"""
Split Tunnel Engine — per-application packet routing via WinDivert.

Uses three threads:
1. Connection Tracker: maps local ports -> exe_path via psutil so the
   interceptors can identify which process owns each packet.
2. Outbound Interceptor: rewrites source IP + interface to route traffic
3. Inbound Interceptor: rewrites destination IP back (reverse NAT) for
   return traffic
"""

import logging
import os
import threading
import time

import psutil

try:
    import pydivert
except ImportError:
    pydivert = None

from core.port_lookup import get_pid_for_tcp_port, get_pid_for_udp_port

log = logging.getLogger(__name__)

# How often to refresh the connection table (seconds)
CONN_POLL_INTERVAL = 0.2

# How many tracker cycles between NAT table cleanups
NAT_CLEANUP_EVERY = 50  # ~10 seconds at 0.2s interval


def _norm_path(p):
    """Normalize exe path for case-insensitive comparison on Windows."""
    return os.path.normcase(p) if p else p


class SplitEngine:
    """
    Per-application split tunneling engine.

    Parameters
    ----------
    mode : str
        "vpn_default" — all traffic through VPN; toggled apps are excluded.
        "direct_default" — all traffic direct; toggled apps go through VPN.
    vpn_ip : str
        IP address of the VPN interface.
    default_ip : str
        IP address of the default (non-VPN) interface.
    toggled_apps : set[str]
        Set of exe paths that are toggled (excluded or included based on mode).
    """

    def __init__(self):
        self._mode = "vpn_default"
        self._vpn_ip = None
        self._default_ip = None
        self._vpn_if_index = None
        self._default_if_index = None
        self._default_gateway = None
        self._toggled_apps = frozenset()

        # Connection tracking tables (atomically swapped, read without lock):
        #   _conn_table: (local_ip, local_port) -> exe_path
        #   _port_table: local_port -> exe_path
        self._conn_table = {}
        self._port_table = {}

        # PID -> exe_path cache (accessed from tracker + interceptor threads;
        # individual dict operations are GIL-safe in CPython)
        self._pid_cache = {}

        # NAT table for return traffic (read without lock, write with lock):
        #   key:   (remote_ip, remote_port, local_port)
        #   value: (original_local_ip, original_if_index)
        self._nat_table = {}
        self._nat_lock = threading.Lock()

        self._stop_event = threading.Event()
        self._threads = []
        self._running = False

        # WinDivert handles (kept for clean shutdown)
        self._outbound_handle = None
        self._inbound_handle = None
        self._handle_lock = threading.Lock()

    @property
    def running(self):
        return self._running

    def start(self, mode, vpn_ip, default_ip, toggled_apps=None,
              vpn_if_index=None, default_if_index=None,
              default_gateway=None):
        """Start the split tunnel engine with the given configuration."""
        if pydivert is None:
            raise RuntimeError(
                "pydivert is not installed. Install it with: pip install pydivert"
            )

        if self._running:
            self.stop()

        self._mode = mode
        self._vpn_ip = vpn_ip
        self._default_ip = default_ip
        self._vpn_if_index = vpn_if_index
        self._default_if_index = default_if_index
        self._default_gateway = default_gateway
        self._toggled_apps = frozenset(_norm_path(p) for p in (toggled_apps or []))

        self._stop_event.clear()
        self._conn_table = {}
        self._port_table = {}
        self._pid_cache = {}
        self._nat_table = {}

        # Add routes through the real gateway so redirected packets
        # have a valid path to the internet on the default interface
        if self._default_gateway and self._default_if_index:
            from core.network_utils import add_split_routes
            add_split_routes(self._default_gateway, self._default_if_index)

        # Start threads
        conn_thread = threading.Thread(
            target=self._connection_tracker_loop, daemon=True, name="ConnTracker"
        )
        out_thread = threading.Thread(
            target=self._outbound_interceptor_loop, daemon=True, name="OutboundIntercept"
        )
        in_thread = threading.Thread(
            target=self._inbound_interceptor_loop, daemon=True, name="InboundIntercept"
        )

        self._threads = [conn_thread, out_thread, in_thread]
        self._running = True

        for t in self._threads:
            t.start()

        log.info(
            f"Split engine started: mode={mode}, vpn_ip={vpn_ip}, "
            f"default_ip={default_ip}, toggled={len(self._toggled_apps)} apps"
        )

    def stop(self):
        """Stop the split tunnel engine and all threads."""
        if not self._running:
            return

        log.info("Stopping split engine...")
        self._stop_event.set()
        self._running = False

        # Remove split-tunnel routes before closing handles
        if self._default_gateway and self._default_if_index:
            from core.network_utils import remove_split_routes
            try:
                remove_split_routes(self._default_gateway, self._default_if_index)
            except Exception:
                pass

        # Close WinDivert handles to unblock recv() calls
        with self._handle_lock:
            for handle in (self._outbound_handle, self._inbound_handle):
                if handle:
                    try:
                        handle.close()
                    except Exception:
                        pass
            self._outbound_handle = None
            self._inbound_handle = None

        # Wait for threads to finish (should be quick now that handles are closed)
        for t in self._threads:
            t.join(timeout=2)

        self._threads = []
        self._nat_table = {}
        self._conn_table = {}
        self._port_table = {}
        self._pid_cache = {}
        log.info("Split engine stopped.")

    def update_policy(self, toggled_apps):
        """Live-update which apps are split. Thread-safe via atomic swap."""
        self._toggled_apps = frozenset(_norm_path(p) for p in toggled_apps)
        log.info(f"Policy updated: {len(self._toggled_apps)} toggled apps")

    def update_mode(self, mode):
        """Update the tunnel mode."""
        self._mode = mode

    # ------------------------------------------------------------------
    # Connection Tracker Thread
    # ------------------------------------------------------------------

    def _resolve_exe(self, pid):
        """Resolve PID to normalized exe path, with caching."""
        exe = self._pid_cache.get(pid)
        if exe is not None:
            return exe
        try:
            proc = psutil.Process(pid)
            raw = proc.exe()
            if raw:
                exe = _norm_path(raw)
                self._pid_cache[pid] = exe
                return exe
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return None

    def _resolve_port_exe(self, port):
        """Synchronous port→exe lookup via Windows IP Helper API.

        Called from the interceptor thread when the connection tracker
        hasn't indexed a port yet (e.g. brand-new TCP SYN).  Queries
        GetExtendedTcpTable / GetExtendedUdpTable directly so there is
        no polling delay.
        """
        try:
            pid = get_pid_for_tcp_port(port)
            if pid is None:
                pid = get_pid_for_udp_port(port)
            if pid:
                return self._resolve_exe(pid)
        except Exception:
            pass
        return None

    def _connection_tracker_loop(self):
        """Poll psutil to maintain a mapping of local sockets to process exe paths."""
        cycles = 0
        while not self._stop_event.is_set():
            try:
                new_table = {}
                new_port_table = {}
                alive_pids = set()

                for conn in psutil.net_connections(kind="inet"):
                    if not conn.laddr or not conn.pid:
                        continue

                    alive_pids.add(conn.pid)
                    exe = self._resolve_exe(conn.pid)
                    if not exe:
                        continue

                    ip = conn.laddr.ip
                    port = conn.laddr.port

                    # Primary table: exact (ip, port) -> exe
                    new_table[(ip, port)] = exe

                    # For sockets bound to 0.0.0.0 / ::, also index under
                    # the actual interface IPs so packets match
                    if ip in ("0.0.0.0", "::"):
                        if self._vpn_ip:
                            new_table[(self._vpn_ip, port)] = exe
                        if self._default_ip:
                            new_table[(self._default_ip, port)] = exe

                    # Port-only fallback (ephemeral ports are unique enough)
                    new_port_table[port] = exe

                # Atomic swap — interceptors read these without locks
                self._conn_table = new_table
                self._port_table = new_port_table

                # Prune PID cache of dead processes
                self._pid_cache = {
                    pid: exe for pid, exe in self._pid_cache.items()
                    if pid in alive_pids
                }

            except Exception as e:
                log.debug(f"Connection tracker error: {e}")

            # Periodically prune the NAT table
            cycles += 1
            if cycles >= NAT_CLEANUP_EVERY:
                cycles = 0
                self.cleanup_nat_table()

            self._stop_event.wait(CONN_POLL_INTERVAL)

    # ------------------------------------------------------------------
    # Outbound Interceptor Thread
    # ------------------------------------------------------------------

    def _outbound_interceptor_loop(self):
        """Intercept outbound packets and rewrite source IP based on policy."""
        # Filter excludes loopback at kernel level — never reaches Python
        try:
            w = pydivert.WinDivert(
                "outbound and ip and (tcp or udp) "
                "and ip.SrcAddr != 127.0.0.1 and ip.DstAddr != 127.0.0.1",
                priority=100,
            )
            w.open()
            with self._handle_lock:
                self._outbound_handle = w
        except Exception as e:
            log.error(f"Failed to open WinDivert for outbound: {e}")
            return

        # Cache instance attrs as locals — avoids self.X dict lookup per packet
        send = w.send
        recv = w.recv
        stop = self._stop_event.is_set

        try:
            while not stop():
                try:
                    packet = recv()
                except Exception:
                    if stop():
                        break
                    continue
                if packet is None:
                    continue

                try:
                    src_ip = packet.src_addr
                    src_port = packet.src_port

                    # ---- FAST PATH: skip packets already on the right iface ----
                    # In vpn_default mode, packets with src=default_ip are
                    # already direct (includes VPN tunnel traffic). Skip.
                    # In direct_default mode, packets with src=vpn_ip are
                    # already on VPN. Skip.
                    mode = self._mode
                    if mode == "vpn_default":
                        if src_ip == self._default_ip:
                            send(packet)
                            continue
                    elif mode == "direct_default":
                        if src_ip == self._vpn_ip:
                            send(packet)
                            continue

                    # ---- MEDIUM PATH: look up process for this connection ----
                    # Lock-free reads of atomically-swapped dicts (GIL)
                    exe = self._conn_table.get((src_ip, src_port))
                    if exe is None:
                        exe = self._port_table.get(src_port)
                    if exe is None:
                        # Synchronous fallback: query Windows TCP/UDP
                        # table directly.  Eliminates the race where the
                        # tracker hasn't polled yet for a brand-new
                        # connection (e.g. the very first SYN packet).
                        exe = self._resolve_port_exe(src_port)
                    if not exe or exe not in self._toggled_apps:
                        send(packet)
                        continue

                    # ---- SLOW PATH: rewrite packet for toggled app ----
                    dst_ip = packet.dst_addr
                    dst_port = packet.dst_port

                    if mode == "vpn_default":
                        new_src_ip = self._default_ip
                        target_if_index = self._default_if_index
                    else:
                        new_src_ip = self._vpn_ip
                        target_if_index = self._vpn_if_index

                    # Save original src IP and interface for inbound NAT
                    orig_if_idx = packet.interface[0]
                    nat_key = (dst_ip, dst_port, src_port)
                    with self._nat_lock:
                        self._nat_table[nat_key] = (src_ip, orig_if_idx)

                    packet.src_addr = new_src_ip

                    # Redirect packet to the correct network interface
                    if target_if_index is not None:
                        packet.interface = (target_if_index, 0)

                    send(packet)

                except Exception as e:
                    if stop():
                        break
                    log.debug(f"Outbound packet error: {e}")
        finally:
            with self._handle_lock:
                self._outbound_handle = None
            try:
                w.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Inbound Interceptor Thread
    # ------------------------------------------------------------------

    def _inbound_interceptor_loop(self):
        """Intercept inbound packets and reverse-NAT destination IP."""
        try:
            w = pydivert.WinDivert(
                "inbound and ip and (tcp or udp) "
                "and ip.SrcAddr != 127.0.0.1 and ip.DstAddr != 127.0.0.1",
                priority=200,
            )
            w.open()
            with self._handle_lock:
                self._inbound_handle = w
        except Exception as e:
            log.error(f"Failed to open WinDivert for inbound: {e}")
            return

        send = w.send
        recv = w.recv
        stop = self._stop_event.is_set

        try:
            while not stop():
                try:
                    packet = recv()
                except Exception:
                    if stop():
                        break
                    continue
                if packet is None:
                    continue

                try:
                    # Lock-free read of NAT table (atomic dict.get via GIL)
                    nat_entry = self._nat_table.get(
                        (packet.src_addr, packet.src_port, packet.dst_port)
                    )

                    if nat_entry:
                        original_ip, original_if_idx = nat_entry
                        if packet.dst_addr != original_ip:
                            packet.dst_addr = original_ip
                            # Deliver on the original interface so the OS
                            # accepts the packet (strong host model)
                            packet.interface = (original_if_idx, 0)

                    send(packet)

                except Exception as e:
                    if stop():
                        break
                    log.debug(f"Inbound packet error: {e}")
        finally:
            with self._handle_lock:
                self._inbound_handle = None
            try:
                w.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # NAT table maintenance
    # ------------------------------------------------------------------

    def cleanup_nat_table(self, max_entries=50000):
        """Prune NAT table if it grows too large. Called periodically."""
        with self._nat_lock:
            if len(self._nat_table) > max_entries:
                # Simple strategy: clear oldest half
                keys = list(self._nat_table.keys())
                for k in keys[: len(keys) // 2]:
                    del self._nat_table[k]
