"""
Custom popup menu — dark-themed CTk dropdown that works as both
menu bar dropdowns and right-click context menus.
"""

import tkinter as tk
import customtkinter as ctk


class PopupMenu(tk.Toplevel):
    """
    A styled popup menu using a borderless Toplevel with CTk widgets.
    Shows with show(x, y) and auto-closes on outside click or Escape.
    """

    def __init__(self, parent, items, width=200):
        """
        items: list of dicts or None (separator).
            {"label": str, "command": callable}
            {"label": str, "command": callable, "checkvar": tk.BooleanVar}
            None  -> separator line
        """
        super().__init__(parent)
        self.withdraw()
        self.overrideredirect(True)
        self.configure(bg="#333333")
        self.attributes("-topmost", True)
        self._parent = parent
        self._click_id = None
        self._dismissed = False

        frame = ctk.CTkFrame(
            self, fg_color="#2b2b2b", corner_radius=8,
            border_width=1, border_color="#555555",
        )
        frame.pack(fill="both", expand=True, padx=0, pady=0)

        for item in items:
            if item is None:
                sep = ctk.CTkFrame(frame, height=1, fg_color="#444444")
                sep.pack(fill="x", padx=10, pady=4)
            elif "checkvar" in item:
                cb = ctk.CTkCheckBox(
                    frame, text=item["label"],
                    variable=item["checkvar"],
                    command=lambda cmd=item["command"]: self._run(cmd),
                    font=("", 13), height=32,
                    fg_color="#bf5af2", hover_color="#9b3dd6",
                    text_color="#e0e0e0",
                    checkbox_width=18, checkbox_height=18,
                )
                cb.pack(anchor="w", fill="x", padx=10, pady=2)
            else:
                btn = ctk.CTkButton(
                    frame, text="  " + item["label"],
                    command=lambda cmd=item["command"]: self._run(cmd),
                    height=32, corner_radius=6, width=width,
                    fg_color="transparent", hover_color="#bf5af2",
                    text_color="#e0e0e0", font=("", 13),
                    anchor="w",
                )
                btn.pack(fill="x", padx=6, pady=2)

        frame.configure(corner_radius=8)

    def show(self, x, y):
        """Show the popup at screen coordinates (x, y)."""
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.lift()
        self.focus_force()
        # Bind global click to close — delayed so current click doesn't trigger it
        self.after(50, self._bind_dismiss)

    def _bind_dismiss(self):
        """Bind events to auto-close the popup."""
        if self._dismissed:
            return
        self._click_id = self._parent.bind_all("<Button-1>", self._on_global_click, add="+")
        self.bind("<Escape>", lambda e: self.dismiss())
        self.bind("<FocusOut>", lambda e: self.after(100, self._check_focus))

    def _check_focus(self):
        """Close if focus left the popup entirely."""
        if self._dismissed:
            return
        try:
            focused = self.focus_get()
            if focused is None or not str(focused).startswith(str(self)):
                self.dismiss()
        except Exception:
            self.dismiss()

    def _on_global_click(self, event):
        """Close popup if click is outside it."""
        if self._dismissed:
            return
        try:
            mx, my = self.winfo_rootx(), self.winfo_rooty()
            mw, mh = self.winfo_width(), self.winfo_height()
            if not (mx <= event.x_root <= mx + mw and my <= event.y_root <= my + mh):
                self.dismiss()
        except Exception:
            self.dismiss()

    def _run(self, command):
        """Execute a menu item command and close."""
        self.dismiss()
        command()

    def dismiss(self):
        """Hide the popup, unbind global handlers, and schedule destruction."""
        if self._dismissed:
            return
        self._dismissed = True
        if self._click_id:
            try:
                self._parent.unbind_all("<Button-1>")
            except Exception:
                pass
            self._click_id = None
        try:
            self.withdraw()
        except Exception:
            pass
        try:
            self.after(200, self.destroy)
        except Exception:
            pass
