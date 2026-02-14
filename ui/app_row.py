"""
App row widget — a single application entry with icon, name, path, and toggle switch.
"""

import os
import subprocess

import customtkinter as ctk
from PIL import Image

from ui.popup_menu import PopupMenu

_MAX_PATH_CHARS = 60
_HOVER_COLOR = "#2a2d2e"
_NORMAL_COLOR = "transparent"


def _truncate_path(path, max_len=_MAX_PATH_CHARS):
    if len(path) <= max_len:
        return path
    return "..." + path[-(max_len - 3):]


class AppRow(ctk.CTkFrame):
    """
    Single row in the app list showing:
    [icon] [app name + exe path] [toggle switch]
    """

    def __init__(self, master, app_name, exe_path, icon_image=None,
                 default_icon=None, mode="vpn_default",
                 initial_state=False, on_toggle=None, pid_count=1,
                 **kwargs):
        super().__init__(master, height=50, fg_color=_NORMAL_COLOR, **kwargs)

        self.exe_path = exe_path
        self._on_toggle = on_toggle
        self._mode = mode
        self._icon_image = icon_image  # keep reference for reuse
        self._app_name = app_name      # raw name without pid badge

        self.grid_columnconfigure(1, weight=1)

        # Icon
        if icon_image:
            ctk_img = ctk.CTkImage(light_image=icon_image, dark_image=icon_image, size=(32, 32))
        elif default_icon:
            ctk_img = ctk.CTkImage(light_image=default_icon, dark_image=default_icon, size=(32, 32))
        else:
            ctk_img = None

        if ctk_img:
            self._icon_label = ctk.CTkLabel(self, image=ctk_img, text="")
            self._icon_label.grid(row=0, column=0, rowspan=2, padx=(10, 5), pady=5)
        else:
            self._icon_label = ctk.CTkLabel(self, text="■", width=32, font=("", 20), text_color="gray")
            self._icon_label.grid(row=0, column=0, rowspan=2, padx=(10, 5), pady=5)

        # App name with process count badge
        display_name = app_name
        if pid_count > 1:
            display_name = f"{app_name}  ({pid_count})"
        self._name_label = ctk.CTkLabel(
            self, text=display_name, font=("", 14, "bold"), anchor="w"
        )
        self._name_label.grid(row=0, column=1, padx=5, pady=(5, 0), sticky="sw")

        # Exe path (small, gray, truncated)
        self._path_label = ctk.CTkLabel(
            self, text=_truncate_path(exe_path), font=("", 10), text_color="gray", anchor="w"
        )
        self._path_label.grid(row=1, column=1, padx=5, pady=(0, 5), sticky="nw")

        # Toggle switch
        switch_text = "Exclude" if mode == "vpn_default" else "Include"
        self._switch_var = ctk.BooleanVar(value=initial_state)
        self._switch = ctk.CTkSwitch(
            self,
            text=switch_text,
            variable=self._switch_var,
            command=self._handle_toggle,
            width=50,
        )
        self._switch.grid(row=0, column=2, rowspan=2, padx=10, pady=5)

        # Hover effect + right-click
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-3>", self._show_context_menu)
        for child in (self._icon_label, self._name_label, self._path_label):
            child.bind("<Enter>", self._on_enter)
            child.bind("<Leave>", self._on_leave)
            child.bind("<Button-3>", self._show_context_menu)

    @property
    def is_toggled(self):
        return self._switch_var.get()

    @property
    def app_name(self):
        return self._app_name

    def set_mode(self, mode):
        self._mode = mode
        switch_text = "Exclude" if mode == "vpn_default" else "Include"
        self._switch.configure(text=switch_text)

    def set_state(self, state):
        self._switch_var.set(state)

    def matches_filter(self, text):
        """Check if this row matches a search filter string."""
        text = text.lower()
        return (
            text in self._name_label.cget("text").lower()
            or text in self.exe_path.lower()
        )

    def _on_enter(self, event=None):
        self.configure(fg_color=_HOVER_COLOR)

    def _on_leave(self, event=None):
        self.configure(fg_color=_NORMAL_COLOR)

    def _handle_toggle(self):
        if self._on_toggle:
            self._on_toggle(self.exe_path, self._switch_var.get())

    def _show_context_menu(self, event):
        menu = PopupMenu(self.winfo_toplevel(), [
            {"label": "Open File Location", "command": self._open_file_location},
            {"label": "Copy Path", "command": self._copy_path},
        ])
        menu.show(event.x_root, event.y_root)

    def _open_file_location(self):
        """Open Explorer with the exe file selected."""
        if os.path.isfile(self.exe_path):
            subprocess.Popen(["explorer", "/select,", self.exe_path])

    def _copy_path(self):
        """Copy the exe path to clipboard."""
        self.clipboard_clear()
        self.clipboard_append(self.exe_path)
