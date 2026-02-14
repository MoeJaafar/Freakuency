"""
Main window — top-level layout assembling all UI frames.
"""

import customtkinter as ctk

from ui.config_frame import ConfigFrame
from ui.app_list_frame import AppListFrame
from ui.status_bar import StatusBar


class MainWindow(ctk.CTk):
    """
    Top-level application window.

    Layout:
        [ConfigFrame]      — start/stop, status, mode toggle
        [AppListFrame]     — scrollable app list with toggles
        [StatusBar]        — split tunnel statistics
    """

    def __init__(self, on_start=None, on_stop=None,
                 on_mode_change=None, on_toggle=None,
                 on_close=None, default_icon=None):
        super().__init__()

        self.title("Split Tunnel")
        self.geometry("700x800")
        self.minsize(500, 500)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Config frame (top)
        self.config_frame = ConfigFrame(
            self,
            on_start=on_start,
            on_stop=on_stop,
            on_mode_change=on_mode_change,
        )
        self.config_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))

        # App list frame (middle, expandable)
        self.app_list = AppListFrame(
            self,
            mode="vpn_default",
            default_icon=default_icon,
            on_toggle=on_toggle,
        )
        self.app_list.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)

        # Status bar (bottom)
        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=2, column=0, sticky="ew", padx=10, pady=(5, 10))

        # Close handler
        if on_close:
            self.protocol("WM_DELETE_WINDOW", on_close)
