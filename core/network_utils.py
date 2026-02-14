"""
Network interface detection utilities.
Finds default and VPN interfaces, IPs, and gateways.
"""

import logging
import subprocess
import re
import psutil

log = logging.getLogger(__name__)

# Known VPN adapter name patterns
_VPN_ADAPTER_PATTERNS = [
    "tap", "tun", "wintun", "openvpn", "vpn",
]

# Cache of adapter name -> description (populated once)
_adapter_descriptions = None

# Cache of adapter name -> ifIndex (populated once)
_adapter_if_indexes = None


def _get_adapter_info():
    """Get adapter Name -> Description and Name -> ifIndex from PowerShell."""
    global _adapter_descriptions, _adapter_if_indexes
    if _adapter_descriptions is not None:
        return
    _adapter_descriptions = {}
    _adapter_if_indexes = {}
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-NetAdapter | Select-Object Name, InterfaceDescription, ifIndex | Format-List"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        name = None
        desc = None
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("Name"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("InterfaceDescription") and name:
                desc = line.split(":", 1)[1].strip()
            elif line.startswith("ifIndex") and name:
                idx_str = line.split(":", 1)[1].strip()
                try:
                    _adapter_if_indexes[name] = int(idx_str)
                except ValueError:
                    pass
                if desc:
                    _adapter_descriptions[name] = desc
                name = None
                desc = None
    except Exception:
        pass


def _get_adapter_descriptions():
    """Get a mapping of adapter Name -> InterfaceDescription."""
    _get_adapter_info()
    return _adapter_descriptions


def get_all_interface_ips():
    """Return dict of {interface_name: ipv4_address} for active interfaces."""
    result = {}
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()

    for name, addr_list in addrs.items():
        if name not in stats or not stats[name].isup:
            continue
        for addr in addr_list:
            if addr.family.name == "AF_INET" and addr.address != "127.0.0.1":
                result[name] = addr.address
                break
    return result


def _is_vpn_adapter(name):
    """Check if an adapter is a VPN adapter by name or description."""
    lower = name.lower()
    if any(pat in lower for pat in _VPN_ADAPTER_PATTERNS):
        return True
    # Also check the interface description (e.g. "TAP-Windows Adapter V9")
    descs = _get_adapter_descriptions()
    desc = descs.get(name, "").lower()
    return any(pat in desc for pat in _VPN_ADAPTER_PATTERNS)


def get_default_interface():
    """Return (interface_name, ip_address) of the default non-VPN interface."""
    interfaces = get_all_interface_ips()
    # Prefer non-VPN adapters
    for name, ip in interfaces.items():
        if not _is_vpn_adapter(name):
            return name, ip
    # Fallback: return first available
    for name, ip in interfaces.items():
        return name, ip
    return None, None


def get_vpn_interface():
    """Return (interface_name, ip_address) of the VPN adapter, or (None, None)."""
    interfaces = get_all_interface_ips()
    for name, ip in interfaces.items():
        if _is_vpn_adapter(name):
            return name, ip
    return None, None


def get_interface_index(adapter_name):
    """Return the Windows ifIndex for the given adapter name, or None."""
    _get_adapter_info()
    return _adapter_if_indexes.get(adapter_name)


def get_default_gateway():
    """Parse the default gateway IP from `route print`."""
    try:
        output = subprocess.check_output(
            ["route", "print", "0.0.0.0"],
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        # Look for lines in the routing table with 0.0.0.0 destination
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
                return parts[2]
    except Exception:
        pass
    return None


def get_gateway_for_interface(interface_ip):
    """
    Return the default gateway that routes through the given local interface IP.
    Parses `route print` and matches on the Interface column.
    """
    try:
        output = subprocess.check_output(
            ["route", "print", "0.0.0.0"],
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        for line in output.splitlines():
            parts = line.split()
            # Columns: Network Destination, Netmask, Gateway, Interface, Metric
            if len(parts) >= 5 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
                if parts[3] == interface_ip:
                    return parts[2]
    except Exception:
        pass
    return None


# ------------------------------------------------------------------
# Route management for split tunnel
# ------------------------------------------------------------------

_SPLIT_ROUTES = [
    ("0.0.0.0", "128.0.0.0"),    # 0.0.0.0/1
    ("128.0.0.0", "128.0.0.0"),  # 128.0.0.0/1
]


def add_split_routes(gateway_ip, if_index):
    """
    Add /1 routes through the real gateway on the default interface.

    These ensure the OS has a valid path for packets that WinDivert
    redirects to the default NIC. A high metric (9999) prevents them
    from interfering with normal VPN routing.
    """
    for dest, mask in _SPLIT_ROUTES:
        try:
            subprocess.run(
                ["route", "add", dest, "mask", mask, gateway_ip,
                 "metric", "9999", "IF", str(if_index)],
                capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            log.info(f"Added route: {dest}/{mask} via {gateway_ip} IF {if_index}")
        except Exception as e:
            log.warning(f"Failed to add route {dest}/{mask}: {e}")


def remove_split_routes(gateway_ip, if_index):
    """Remove the split tunnel routes added by add_split_routes()."""
    for dest, mask in _SPLIT_ROUTES:
        try:
            subprocess.run(
                ["route", "delete", dest, "mask", mask, gateway_ip,
                 "IF", str(if_index)],
                capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            log.info(f"Removed route: {dest}/{mask} via {gateway_ip} IF {if_index}")
        except Exception as e:
            log.debug(f"Failed to remove route {dest}/{mask}: {e}")


def wait_for_vpn_interface(timeout=30):
    """
    Poll for a VPN interface to appear. Returns (name, ip) or (None, None).
    Used after VPN connection is established to detect the assigned IP.
    """
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        name, ip = get_vpn_interface()
        if ip:
            return name, ip
        time.sleep(0.5)
    return None, None
