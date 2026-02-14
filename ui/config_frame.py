"""
Config frame — Freakuency controls: Start/Stop, status, mode toggle, VPN info.
"""

import customtkinter as ctk

from ui.logo import render_logo_banner


# Simplified state colors
_STATE_COLORS = {
    "INACTIVE": "#FF4444",   # Red
    "ACTIVE":   "#44FF44",   # Green
    "NO_VPN":   "#FFAA00",   # Orange
}

_ACCENT_COLOR = "#bf5af2"    # Brand purple


class ConfigFrame(ctk.CTkFrame):
    """
    Top section of the UI with branding header, Start/Stop button,
    status indicator, detected VPN info, mode selector, and toggled count.
    """

    def __init__(self, master, on_start=None, on_stop=None,
                 on_mode_change=None, **kwargs):
        super().__init__(master, **kwargs)

        self._on_start = on_start
        self._on_stop = on_stop
        self._on_mode_change = on_mode_change
        self._active = False

        self.grid_columnconfigure(0, weight=1)

        # Row 0: Logo banner
        brand_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=8)
        brand_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 2))

        logo_pil = render_logo_banner(width=500, height=110)
        self._logo_image = ctk.CTkImage(
            light_image=logo_pil, dark_image=logo_pil,
            size=(500, 110),
        )
        self._brand_label = ctk.CTkLabel(
            brand_frame, image=self._logo_image, text="",
        )
        self._brand_label.pack(pady=5)

        # Row 1: Status indicator + VPN info + Start/Stop button
        status_frame = ctk.CTkFrame(self, fg_color="#1e1e1e", corner_radius=8)
        status_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 5))
        status_frame.grid_columnconfigure(1, weight=1)

        self._status_dot = ctk.CTkLabel(
            status_frame, text="●", font=("", 16),
            text_color=_STATE_COLORS["INACTIVE"],
        )
        self._status_dot.grid(row=0, column=0, padx=(10, 5), pady=8)

        self._status_label = ctk.CTkLabel(
            status_frame, text="Inactive", anchor="w"
        )
        self._status_label.grid(row=0, column=1, sticky="w")

        self._start_btn = ctk.CTkButton(
            status_frame, text="Start", width=120,
            command=self._handle_start,
        )
        self._start_btn.grid(row=0, column=2, padx=10, pady=8)

        # Row 2: Detected VPN info
        self._vpn_info_label = ctk.CTkLabel(
            self, text="", font=("", 12), text_color="gray", anchor="w"
        )
        self._vpn_info_label.grid(row=2, column=0, sticky="ew",
                                   padx=15, pady=(0, 5))

        # Row 3: Mode selector + toggled count
        mode_frame = ctk.CTkFrame(self, fg_color="transparent")
        mode_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(5, 5))
        mode_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(mode_frame, text="Tunnel Mode:").grid(row=0, column=0, padx=(0, 10))

        self._mode_var = ctk.StringVar(value="vpn_default")
        self._mode_selector = ctk.CTkSegmentedButton(
            mode_frame,
            values=["VPN Default (Exclude)", "Direct Default (Include)"],
            command=self._handle_mode_change,
        )
        self._mode_selector.set("VPN Default (Exclude)")
        self._mode_selector.grid(row=0, column=1, sticky="ew")

        # Row 4: Toggled count badge
        self._toggled_count_label = ctk.CTkLabel(
            self, text="", font=("", 12), text_color="#888888", anchor="w"
        )
        self._toggled_count_label.grid(row=4, column=0, sticky="ew",
                                        padx=15, pady=(0, 10))

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
                text_color="#bf5af2",
            )
        else:
            self._vpn_info_label.configure(text="", text_color="gray")

    def update_toggled_count(self, count):
        """Update the toggled count badge label."""
        if count == 0:
            self._toggled_count_label.configure(text="")
        else:
            mode = self._mode_var.get()
            action = "excluded" if mode == "vpn_default" else "included"
            noun = "app" if count == 1 else "apps"
            self._toggled_count_label.configure(
                text=f"{count} {noun} {action}",
                text_color=_ACCENT_COLOR,
            )

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
                fg_color="#7c3aad", hover_color="#5a2880",
                command=self._handle_start,
                state="normal",
            )
        else:  # INACTIVE
            self._status_label.configure(text="Inactive")
            self._active = False
            self._start_btn.configure(
                text="Start",
                fg_color="#7c3aad", hover_color="#5a2880",
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
