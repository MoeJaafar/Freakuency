"""
App row widget — a single application entry with icon, name, path, and toggle switch.
"""

import customtkinter as ctk
from PIL import Image


class AppRow(ctk.CTkFrame):
    """
    Single row in the app list showing:
    [icon] [app name + exe path] [toggle switch]
    """

    def __init__(self, master, app_name, exe_path, icon_image=None,
                 default_icon=None, mode="vpn_default",
                 initial_state=False, on_toggle=None, **kwargs):
        super().__init__(master, height=50, **kwargs)

        self.exe_path = exe_path
        self._on_toggle = on_toggle
        self._mode = mode

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

        # App name
        self._name_label = ctk.CTkLabel(
            self, text=app_name, font=("", 14, "bold"), anchor="w"
        )
        self._name_label.grid(row=0, column=1, padx=5, pady=(5, 0), sticky="sw")

        # Exe path (small, gray)
        self._path_label = ctk.CTkLabel(
            self, text=exe_path, font=("", 10), text_color="gray", anchor="w"
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

    @property
    def is_toggled(self):
        return self._switch_var.get()

    @property
    def app_name(self):
        return self._name_label.cget("text")

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

    def _handle_toggle(self):
        if self._on_toggle:
            self._on_toggle(self.exe_path, self._switch_var.get())
