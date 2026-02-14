"""
Split Tunnel VPN — Application controller.
Detects a running VPN connection and manages the split tunnel engine.
Handles persistence of user settings.
"""

import json
import logging
import os
import threading

import psutil
from PIL import Image

from core.split_engine import SplitEngine
from core.network_utils import (
    get_default_interface, get_vpn_interface, get_interface_index,
    get_gateway_for_interface,
)
from ui.main_window import MainWindow

log = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


class SplitTunnelApp:
    """Main application controller."""

    def __init__(self):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        )

        self._engine = SplitEngine()
        self._stats_job = None
        self._vpn_iface_name = None
        self._baseline_bytes_in = 0
        self._baseline_bytes_out = 0

        # Load default icon
        default_icon = self._load_default_icon()

        # Create the window
        self._window = MainWindow(
            on_start=self._on_start,
            on_stop=self._on_stop,
            on_mode_change=self._on_mode_change,
            on_toggle=self._on_app_toggle,
            on_close=self._on_close,
            default_icon=default_icon,
        )

        # Restore persisted settings
        self._load_config()

    def run(self):
        """Start the application main loop."""
        self._window.mainloop()

    # ------------------------------------------------------------------
    # Config persistence
    # ------------------------------------------------------------------

    def _load_config(self):
        """Load persisted settings from config.json."""
        if not os.path.isfile(CONFIG_PATH):
            return

        try:
            with open(CONFIG_PATH, "r") as f:
                cfg = json.load(f)

            mode = cfg.get("mode", "vpn_default")
            self._window.config_frame.set_mode(mode)
            self._window.app_list.set_mode(mode)

            toggled = cfg.get("toggled_apps", [])
            self._window.app_list.set_toggled_apps(toggled)

            log.info(f"Config loaded: mode={mode}, toggled={len(toggled)} apps")
        except Exception as e:
            log.warning(f"Failed to load config: {e}")

    def _save_config(self):
        """Persist current settings to config.json."""
        try:
            cfg = {
                "mode": self._window.config_frame.mode,
                "toggled_apps": list(self._window.app_list.get_toggled_apps()),
            }
            with open(CONFIG_PATH, "w") as f:
                json.dump(cfg, f, indent=2)
        except Exception as e:
            log.warning(f"Failed to save config: {e}")

    # ------------------------------------------------------------------
    # Start / Stop split tunneling
    # ------------------------------------------------------------------

    def _on_start(self):
        """User clicked Start — detect VPN and start split engine."""
        def _do_start():
            vpn_name, vpn_ip = get_vpn_interface()
            default_name, default_ip = get_default_interface()

            if not vpn_ip:
                self._window.after(0, self._show_error,
                    "No VPN detected.\n\n"
                    "Connect to a VPN using your VPN client first, "
                    "then click Start.")
                self._window.after(0, self._window.config_frame.update_state,
                    "NO_VPN", "")
                return

            if not default_ip:
                self._window.after(0, self._show_error,
                    "Could not detect default network interface.")
                return

            self._vpn_iface_name = vpn_name

            # Get interface indexes for packet redirection
            vpn_if_index = get_interface_index(vpn_name)
            default_if_index = get_interface_index(default_name)

            if vpn_if_index is None or default_if_index is None:
                log.warning(
                    f"Could not resolve interface indexes: "
                    f"vpn={vpn_if_index}, default={default_if_index}. "
                    f"Packet redirection may not work."
                )

            # Get the real default gateway (for the non-VPN interface)
            default_gateway = get_gateway_for_interface(default_ip)
            if not default_gateway:
                log.warning(
                    "Could not detect default gateway for the non-VPN interface. "
                    "Split tunnel routing may not work."
                )

            # Capture baseline NIC counters so we show delta from now
            self._capture_baseline()

            mode = self._window.config_frame.mode
            toggled = self._window.app_list.get_toggled_apps()

            try:
                self._engine.start(
                    mode, vpn_ip, default_ip, toggled,
                    vpn_if_index=vpn_if_index,
                    default_if_index=default_if_index,
                    default_gateway=default_gateway,
                )
                log.info(f"Split engine started: vpn={vpn_name} ({vpn_ip}, idx={vpn_if_index}), "
                         f"default={default_name} ({default_ip}, idx={default_if_index}), "
                         f"gateway={default_gateway}")
            except Exception as e:
                log.error(f"Failed to start split engine: {e}")
                self._window.after(0, self._show_error,
                    f"Split tunnel engine error:\n{e}")
                return

            # Update UI on main thread
            def _update_ui():
                self._window.config_frame.set_vpn_info(vpn_name, vpn_ip)
                self._window.config_frame.update_state("ACTIVE", "")
                self._window.status_bar.set_vpn_adapter(vpn_name, vpn_ip)
                self._window.status_bar.set_connected()
                self._start_stats_polling()

            self._window.after(0, _update_ui)

        threading.Thread(target=_do_start, daemon=True).start()

    def _on_stop(self):
        """User clicked Stop — stop split engine (VPN stays connected)."""
        def _do_stop():
            self._stop_split_engine()
            self._window.after(0, self._on_stopped)

        threading.Thread(target=_do_stop, daemon=True).start()

    def _on_stopped(self):
        """Update UI after engine stops."""
        self._stop_stats_polling()
        self._window.config_frame.update_state("INACTIVE", "")
        self._window.config_frame.set_vpn_info(None, None)
        self._window.status_bar.reset()
        self._save_config()

    # ------------------------------------------------------------------
    # Split tunnel engine
    # ------------------------------------------------------------------

    def _stop_split_engine(self):
        if self._engine.running:
            self._engine.stop()

    # ------------------------------------------------------------------
    # Mode & toggle changes
    # ------------------------------------------------------------------

    def _on_mode_change(self, mode):
        """User switched tunnel mode."""
        self._window.app_list.set_mode(mode)

        if self._engine.running:
            self._engine.update_mode(mode)

        self._save_config()

    def _on_app_toggle(self, exe_path, state):
        """User toggled an app's split tunnel switch."""
        if self._engine.running:
            toggled = self._window.app_list.get_toggled_apps()
            self._engine.update_policy(toggled)
        self._save_config()

    # ------------------------------------------------------------------
    # Stats polling (NIC counters via psutil)
    # ------------------------------------------------------------------

    def _capture_baseline(self):
        """Record current NIC counters so stats show delta from start."""
        try:
            counters = psutil.net_io_counters(pernic=True)
            if self._vpn_iface_name and self._vpn_iface_name in counters:
                nic = counters[self._vpn_iface_name]
                self._baseline_bytes_in = nic.bytes_recv
                self._baseline_bytes_out = nic.bytes_sent
            else:
                self._baseline_bytes_in = 0
                self._baseline_bytes_out = 0
        except Exception:
            self._baseline_bytes_in = 0
            self._baseline_bytes_out = 0

    def _start_stats_polling(self):
        self._poll_stats()

    def _stop_stats_polling(self):
        if self._stats_job:
            self._window.after_cancel(self._stats_job)
            self._stats_job = None

    def _poll_stats(self):
        """Fetch VPN NIC traffic stats and schedule next poll."""
        if self._engine.running and self._vpn_iface_name:
            try:
                counters = psutil.net_io_counters(pernic=True)
                if self._vpn_iface_name in counters:
                    nic = counters[self._vpn_iface_name]
                    bytes_in = nic.bytes_recv - self._baseline_bytes_in
                    bytes_out = nic.bytes_sent - self._baseline_bytes_out
                    self._window.status_bar.update_stats(bytes_in, bytes_out)
            except Exception:
                pass
        self._stats_job = self._window.after(2000, self._poll_stats)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def _on_close(self):
        """Window close handler — clean up everything."""
        self._save_config()
        self._stop_stats_polling()
        try:
            self._stop_split_engine()
        except Exception:
            pass
        self._window.destroy()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_default_icon(self):
        """Load the default fallback icon from assets."""
        path = os.path.join(ASSETS_DIR, "default_icon.png")
        if os.path.isfile(path):
            try:
                return Image.open(path).resize((32, 32))
            except Exception:
                pass
        return None

    def _show_error(self, message):
        """Show an error dialog to the user."""
        try:
            from tkinter import messagebox
            messagebox.showerror("Split Tunnel — Error", message)
        except Exception:
            log.error(f"Error dialog: {message}")
