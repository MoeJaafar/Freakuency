"""
Status bar — shows split tunnel stats at the bottom of the window.
"""

import customtkinter as ctk


class StatusBar(ctk.CTkFrame):
    """Bottom bar showing split tunnel statistics."""

    def __init__(self, master, **kwargs):
        super().__init__(master, height=40, **kwargs)

        self.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self._adapter_label = ctk.CTkLabel(
            self, text="VPN: —", font=("", 12), text_color="gray"
        )
        self._adapter_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self._duration_label = ctk.CTkLabel(
            self, text="Duration: —", font=("", 12), text_color="gray"
        )
        self._duration_label.grid(row=0, column=1, padx=10, pady=5)

        self._download_label = ctk.CTkLabel(
            self, text="↓ 0 B", font=("", 12), text_color="gray"
        )
        self._download_label.grid(row=0, column=2, padx=10, pady=5)

        self._upload_label = ctk.CTkLabel(
            self, text="↑ 0 B", font=("", 12), text_color="gray"
        )
        self._upload_label.grid(row=0, column=3, padx=10, pady=5, sticky="e")

        self._connected = False
        self._update_job = None

    def set_vpn_adapter(self, adapter_name, vpn_ip):
        """Display detected VPN adapter name and IP."""
        self._adapter_label.configure(text=f"VPN: {adapter_name} ({vpn_ip})")

    def set_connected(self):
        self._connected = True
        self._start_timer()

    def update_stats(self, bytes_in, bytes_out):
        self._download_label.configure(text=f"↓ {self._format_bytes(bytes_in)}")
        self._upload_label.configure(text=f"↑ {self._format_bytes(bytes_out)}")

    def reset(self):
        self._adapter_label.configure(text="VPN: —")
        self._duration_label.configure(text="Duration: —")
        self._download_label.configure(text="↓ 0 B")
        self._upload_label.configure(text="↑ 0 B")
        self._connected = False
        if self._update_job:
            self.after_cancel(self._update_job)
            self._update_job = None

    def _start_timer(self):
        import time
        self._connect_time = time.monotonic()
        self._tick()

    def _tick(self):
        if not self._connected:
            return
        import time
        elapsed = int(time.monotonic() - self._connect_time)
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        self._duration_label.configure(
            text=f"Duration: {hours:02d}:{minutes:02d}:{seconds:02d}"
        )
        self._update_job = self.after(1000, self._tick)

    @staticmethod
    def _format_bytes(n):
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
            n /= 1024
        return f"{n:.1f} TB"
