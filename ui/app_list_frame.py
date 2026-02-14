"""
App list frame — scrollable list of running applications with toggle switches.
"""

import threading
import customtkinter as ctk

from ui.app_row import AppRow
from core.process_scanner import scan_processes, extract_icon


class AppListFrame(ctk.CTkFrame):
    """
    Middle section of the UI: search bar + scrollable list of app rows.
    """

    def __init__(self, master, mode="vpn_default", default_icon=None,
                 on_toggle=None, **kwargs):
        super().__init__(master, **kwargs)

        self._mode = mode
        self._default_icon = default_icon
        self._on_toggle = on_toggle
        self._rows = []            # list of AppRow widgets
        self._toggled_apps = {}    # exe_path -> bool

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Top bar: search + refresh
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 0))
        top_bar.grid_columnconfigure(0, weight=1)

        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", self._on_search_changed)
        self._search_entry = ctk.CTkEntry(
            top_bar, placeholder_text="Search apps...",
            textvariable=self._search_var,
        )
        self._search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self._refresh_btn = ctk.CTkButton(
            top_bar, text="Refresh", width=80, command=self.refresh_apps
        )
        self._refresh_btn.grid(row=0, column=1)

        # Scrollable app list
        self._scroll_frame = ctk.CTkScrollableFrame(self)
        self._scroll_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self._scroll_frame.grid_columnconfigure(0, weight=1)

        # Loading label
        self._loading_label = ctk.CTkLabel(
            self._scroll_frame, text="Click Refresh to scan running apps...",
            text_color="gray",
        )
        self._loading_label.grid(row=0, column=0, pady=20)

    def set_mode(self, mode):
        self._mode = mode
        for row in self._rows:
            row.set_mode(mode)

    def set_toggled_apps(self, toggled_apps):
        """Restore toggled state from persisted config."""
        self._toggled_apps = {path: True for path in toggled_apps}
        for row in self._rows:
            row.set_state(row.exe_path in self._toggled_apps)

    def get_toggled_apps(self):
        """Return set of exe paths that are currently toggled on."""
        return {row.exe_path for row in self._rows if row.is_toggled}

    def refresh_apps(self):
        """Scan running processes and rebuild the app list."""
        self._refresh_btn.configure(state="disabled", text="Scanning...")
        self._loading_label.configure(text="Scanning processes...")
        self._loading_label.grid(row=0, column=0, pady=20)

        # Clear existing rows
        for row in self._rows:
            row.destroy()
        self._rows.clear()

        # Scan in background thread
        thread = threading.Thread(target=self._scan_and_build, daemon=True)
        thread.start()

    def _scan_and_build(self):
        """Background thread: scan processes and extract icons."""
        processes = scan_processes()

        # Build rows on the main thread
        self.after(0, lambda: self._populate_rows(processes))

    def _populate_rows(self, processes):
        """Create AppRow widgets for each process (runs on main thread)."""
        self._loading_label.grid_forget()

        for i, proc in enumerate(processes):
            icon = extract_icon(proc.exe_path)
            initial_state = proc.exe_path in self._toggled_apps

            row = AppRow(
                self._scroll_frame,
                app_name=proc.name,
                exe_path=proc.exe_path,
                icon_image=icon,
                default_icon=self._default_icon,
                mode=self._mode,
                initial_state=initial_state,
                on_toggle=self._handle_toggle,
            )
            row.grid(row=i, column=0, sticky="ew", pady=1)
            self._rows.append(row)

        self._refresh_btn.configure(state="normal", text="Refresh")

        # Apply current search filter
        self._apply_filter()

    def _handle_toggle(self, exe_path, state):
        """Called when user toggles an app switch."""
        if state:
            self._toggled_apps[exe_path] = True
        else:
            self._toggled_apps.pop(exe_path, None)

        if self._on_toggle:
            self._on_toggle(exe_path, state)

    def _on_search_changed(self, *args):
        self._apply_filter()

    def _apply_filter(self):
        text = self._search_var.get().strip()
        for row in self._rows:
            if not text or row.matches_filter(text):
                row.grid()
            else:
                row.grid_remove()
