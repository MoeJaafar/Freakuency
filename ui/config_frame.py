"""
Config frame — split tunnel controls: Start/Stop, status, mode toggle, VPN info.
"""

import customtkinter as ctk


# Simplified state colors
_STATE_COLORS = {
    "INACTIVE": "#FF4444",   # Red
    "ACTIVE":   "#44FF44",   # Green
    "NO_VPN":   "#FFAA00",   # Orange
}


class ConfigFrame(ctk.CTkFrame):
    """
    Top section of the UI with Start/Stop button, status indicator,
    detected VPN info, and tunnel mode selector.
    """

    def __init__(self, master, on_start=None, on_stop=None,
                 on_mode_change=None, **kwargs):
        super().__init__(master, **kwargs)

        self._on_start = on_start
        self._on_stop = on_stop
        self._on_mode_change = on_mode_change
        self._active = False

        self.grid_columnconfigure(1, weight=1)

        # Row 0: Status indicator + VPN info + Start/Stop button
        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 5))
        status_frame.grid_columnconfigure(1, weight=1)

        self._status_dot = ctk.CTkLabel(
            status_frame, text="●", font=("", 16),
            text_color=_STATE_COLORS["INACTIVE"],
        )
        self._status_dot.grid(row=0, column=0, padx=(0, 5))

        self._status_label = ctk.CTkLabel(
            status_frame, text="Inactive", anchor="w"
        )
        self._status_label.grid(row=0, column=1, sticky="w")

        self._start_btn = ctk.CTkButton(
            status_frame, text="Start", width=120,
            command=self._handle_start,
            fg_color="#2B7A0B", hover_color="#1E5C08",
        )
        self._start_btn.grid(row=0, column=2, padx=(10, 0))

        # Row 1: Detected VPN info
        self._vpn_info_label = ctk.CTkLabel(
            self, text="", font=("", 12), text_color="gray", anchor="w"
        )
        self._vpn_info_label.grid(row=1, column=0, columnspan=2, sticky="ew",
                                   padx=15, pady=(0, 5))

        # Row 2: Mode selector
        mode_frame = ctk.CTkFrame(self, fg_color="transparent")
        mode_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(5, 10))

        ctk.CTkLabel(mode_frame, text="Tunnel Mode:").pack(side="left", padx=(0, 10))

        self._mode_var = ctk.StringVar(value="vpn_default")
        self._mode_selector = ctk.CTkSegmentedButton(
            mode_frame,
            values=["VPN Default (Exclude)", "Direct Default (Include)"],
            command=self._handle_mode_change,
        )
        self._mode_selector.set("VPN Default (Exclude)")
        self._mode_selector.pack(side="left", fill="x", expand=True)

    @property
    def mode(self):
        return self._mode_var.get()

    def set_mode(self, mode):
        self._mode_var.set(mode)
        label = "VPN Default (Exclude)" if mode == "vpn_default" else "Direct Default (Include)"
        self._mode_selector.set(label)

    def set_vpn_info(self, adapter_name, vpn_ip):
        """Show detected VPN adapter info."""
        if adapter_name and vpn_ip:
            self._vpn_info_label.configure(
                text=f"VPN: {vpn_ip} on {adapter_name}",
                text_color="#AAAAFF",
            )
        else:
            self._vpn_info_label.configure(text="", text_color="gray")

    def update_state(self, state, message=""):
        """Update the status display. States: ACTIVE, INACTIVE, NO_VPN."""
        color = _STATE_COLORS.get(state, "#FF4444")
        self._status_dot.configure(text_color=color)

        if state == "ACTIVE":
            self._status_label.configure(text="Active")
            self._active = True
            self._start_btn.configure(
                text="Stop",
                fg_color="#AA2222", hover_color="#881111",
                command=self._handle_stop,
                state="normal",
            )
        elif state == "NO_VPN":
            self._status_label.configure(text="No VPN detected")
            self._active = False
            self._start_btn.configure(
                text="Start",
                fg_color="#2B7A0B", hover_color="#1E5C08",
                command=self._handle_start,
                state="normal",
            )
        else:  # INACTIVE
            self._status_label.configure(text="Inactive")
            self._active = False
            self._start_btn.configure(
                text="Start",
                fg_color="#2B7A0B", hover_color="#1E5C08",
                command=self._handle_start,
                state="normal",
            )

    def _handle_start(self):
        # Disable button while detecting VPN
        self._start_btn.configure(state="disabled")
        self._status_label.configure(text="Detecting VPN...")
        self._status_dot.configure(text_color="#FFAA00")
        if self._on_start:
            self._on_start()

    def _handle_stop(self):
        if self._on_stop:
            self._on_stop()

    def _handle_mode_change(self, value):
        if value == "VPN Default (Exclude)":
            self._mode_var.set("vpn_default")
        else:
            self._mode_var.set("direct_default")

        if self._on_mode_change:
            self._on_mode_change(self._mode_var.get())
