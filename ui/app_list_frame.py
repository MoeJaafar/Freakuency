"""
App list frame — tabbed view (Active / Apps / All Processes) with toggle switches.
"""

import os
import threading
import customtkinter as ctk

from ui.app_row import AppRow
from core.process_scanner import scan_processes, scan_windowed_apps, extract_icon


class AppListFrame(ctk.CTkFrame):
    """
    Middle section of the UI: search bar + tabbed list of app rows.

    Layout:
        [Search...] [Toggle All] [Refresh]
        ┌─── Active ────┬─── Apps ──────┬─── All Processes ───┐
        │               │               │                      │
        └───────────────┴───────────────┴──────────────────────┘
    """

    def __init__(self, master, mode="vpn_default", default_icon=None,
                 on_toggle=None, on_toggled_count_change=None, **kwargs):
        super().__init__(master, **kwargs)

        self._mode = mode
        self._default_icon = default_icon
        self._on_toggle = on_toggle
        self._on_toggled_count_change = on_toggled_count_change
        self._active_rows = []         # AppRow widgets in "Active" tab
        self._apps_rows = []           # AppRow widgets in "Apps" tab
        self._all_rows = []            # AppRow widgets in "All Processes" tab
        self._toggled_apps = {}        # exe_path -> bool (shared state)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Top bar: search + toggle all + refresh
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

        self._toggle_all_btn = ctk.CTkButton(
            top_bar, text="Toggle All", width=90,
            command=self._toggle_all,
            fg_color="#555555", hover_color="#666666",
        )
        self._toggle_all_btn.grid(row=0, column=1, padx=(0, 5))

        self._refresh_btn = ctk.CTkButton(
            top_bar, text="Refresh", width=80, command=self.refresh_apps
        )
        self._refresh_btn.grid(row=0, column=2)

        # Tabview
        self._tabview = ctk.CTkTabview(self)
        self._tabview.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        self._tab_active = self._tabview.add("Active")
        self._tab_apps = self._tabview.add("Apps")
        self._tab_all = self._tabview.add("All Processes")

        # Scrollable frames inside each tab
        self._tab_active.grid_columnconfigure(0, weight=1)
        self._tab_active.grid_rowconfigure(0, weight=1)
        self._active_scroll = ctk.CTkScrollableFrame(self._tab_active)
        self._active_scroll.grid(row=0, column=0, sticky="nsew")
        self._active_scroll.grid_columnconfigure(0, weight=1)

        self._tab_apps.grid_columnconfigure(0, weight=1)
        self._tab_apps.grid_rowconfigure(0, weight=1)
        self._apps_scroll = ctk.CTkScrollableFrame(self._tab_apps)
        self._apps_scroll.grid(row=0, column=0, sticky="nsew")
        self._apps_scroll.grid_columnconfigure(0, weight=1)

        self._tab_all.grid_columnconfigure(0, weight=1)
        self._tab_all.grid_rowconfigure(0, weight=1)
        self._all_scroll = ctk.CTkScrollableFrame(self._tab_all)
        self._all_scroll.grid(row=0, column=0, sticky="nsew")
        self._all_scroll.grid_columnconfigure(0, weight=1)

        # Placeholder / loading labels
        self._active_empty = ctk.CTkLabel(
            self._active_scroll, text="No apps excluded yet.",
            text_color="gray",
        )
        self._active_empty.grid(row=0, column=0, pady=20)

        self._apps_loading = ctk.CTkLabel(
            self._apps_scroll, text="Click Refresh to scan running apps...",
            text_color="gray",
        )
        self._apps_loading.grid(row=0, column=0, pady=20)

        self._all_loading = ctk.CTkLabel(
            self._all_scroll, text="Click Refresh to scan running apps...",
            text_color="gray",
        )
        self._all_loading.grid(row=0, column=0, pady=20)

    def set_mode(self, mode):
        self._mode = mode
        label = "No apps excluded yet." if mode == "vpn_default" else "No apps included yet."
        self._active_empty.configure(text=label)
        for row in self._active_rows + self._apps_rows + self._all_rows:
            row.set_mode(mode)

    def set_toggled_apps(self, toggled_apps):
        """Restore toggled state from persisted config."""
        self._toggled_apps = {path: True for path in toggled_apps}
        for row in self._apps_rows + self._all_rows:
            row.set_state(row.exe_path in self._toggled_apps)
        self._rebuild_active_tab()
        self._notify_toggled_count()

    def get_toggled_apps(self):
        """Return set of exe paths that are currently toggled on."""
        return set(self._toggled_apps.keys())

    def refresh_apps(self):
        """Scan running processes and rebuild both tab lists."""
        self._refresh_btn.configure(state="disabled", text="Scanning...")
        self._toggle_all_btn.configure(state="disabled")

        # Show loading in both tabs
        self._apps_loading.configure(text="Scanning processes...")
        self._apps_loading.grid(row=0, column=0, pady=20)
        self._all_loading.configure(text="Scanning processes...")
        self._all_loading.grid(row=0, column=0, pady=20)

        # Clear existing rows
        for row in self._apps_rows:
            row.destroy()
        self._apps_rows.clear()
        for row in self._all_rows:
            row.destroy()
        self._all_rows.clear()

        # Scan in background thread
        thread = threading.Thread(target=self._scan_and_build, daemon=True)
        thread.start()

    def _scan_and_build(self):
        """Background thread: scan both process lists."""
        windowed = scan_windowed_apps()
        all_procs = scan_processes()
        # Icon extraction must happen on main thread (Win32 GDI/COM requirement)
        self.after(0, lambda: self._populate_both(windowed, all_procs))

    def _populate_both(self, windowed, all_procs):
        """Create AppRow widgets for both tabs in batches (runs on main thread)."""
        self._apps_loading.grid_forget()
        self._all_loading.grid_forget()

        # Build flat list of (parent, proc_list, row_list) work items
        all_work = []
        for proc in windowed:
            all_work.append(("apps", proc))
        for proc in all_procs:
            all_work.append(("all", proc))

        if not windowed:
            self._apps_loading.configure(text="No windowed applications found.")
            self._apps_loading.grid(row=0, column=0, pady=20)

        self._batch_idx = 0
        self._batch_work = all_work
        self._batch_apps_idx = 0
        self._batch_all_idx = 0
        self._process_batch()

    def _process_batch(self):
        """Create a batch of AppRow widgets, then yield to the event loop."""
        BATCH_SIZE = 8
        work = self._batch_work
        end = min(self._batch_idx + BATCH_SIZE, len(work))

        for i in range(self._batch_idx, end):
            tab, proc = work[i]
            icon = extract_icon(proc.exe_path)  # hits cache (pre-extracted)
            initial_state = proc.exe_path in self._toggled_apps
            if tab == "apps":
                row = AppRow(
                    self._apps_scroll,
                    app_name=proc.name, exe_path=proc.exe_path,
                    icon_image=icon, default_icon=self._default_icon,
                    mode=self._mode, initial_state=initial_state,
                    on_toggle=self._handle_toggle, pid_count=len(proc.pids),
                )
                row.grid(row=self._batch_apps_idx, column=0, sticky="ew", pady=1)
                self._apps_rows.append(row)
                self._batch_apps_idx += 1
            else:
                row = AppRow(
                    self._all_scroll,
                    app_name=proc.name, exe_path=proc.exe_path,
                    icon_image=icon, default_icon=self._default_icon,
                    mode=self._mode, initial_state=initial_state,
                    on_toggle=self._handle_toggle, pid_count=len(proc.pids),
                )
                row.grid(row=self._batch_all_idx, column=0, sticky="ew", pady=1)
                self._all_rows.append(row)
                self._batch_all_idx += 1

        self._batch_idx = end

        if self._batch_idx < len(work):
            # Yield to event loop, then continue
            self.after(1, self._process_batch)
        else:
            # All done — finalize
            self._sort_rows_toggled_first(self._apps_rows, self._apps_scroll)
            self._sort_rows_toggled_first(self._all_rows, self._all_scroll)
            self._refresh_btn.configure(state="normal", text="Refresh")
            self._toggle_all_btn.configure(state="normal")
            self._apply_filter()
            self._notify_toggled_count()
            # Rebuild Active tab so it picks up freshly cached icons
            self._rebuild_active_tab()

    def _handle_toggle(self, exe_path, state):
        """Called when user toggles an app switch — sync across all tabs."""
        if state:
            self._toggled_apps[exe_path] = True
        else:
            self._toggled_apps.pop(exe_path, None)

        # Sync toggle state across Apps and All Processes tabs
        for row in self._apps_rows + self._all_rows:
            if row.exe_path == exe_path:
                if row.is_toggled != state:
                    row.set_state(state)

        self._rebuild_active_tab()
        self._notify_toggled_count()

        if self._on_toggle:
            self._on_toggle(exe_path, state)

    def _toggle_all(self):
        """Toggle all visible apps in the current tab."""
        active_tab = self._tabview.get()
        if active_tab == "Active":
            rows = self._active_rows
        elif active_tab == "Apps":
            rows = self._apps_rows
        else:
            rows = self._all_rows

        # Get visible rows
        search_text = self._search_var.get().strip()
        visible = [r for r in rows if not search_text or r.matches_filter(search_text)]

        if not visible:
            return

        # If any are un-toggled, toggle them all on; otherwise toggle all off
        any_off = any(not r.is_toggled for r in visible)
        new_state = any_off

        for row in visible:
            if row.is_toggled != new_state:
                row.set_state(new_state)
                self._handle_toggle(row.exe_path, new_state)

    def _on_search_changed(self, *args):
        self._apply_filter()

    def _apply_filter(self):
        text = self._search_var.get().strip()
        for row in self._active_rows:
            if not text or row.matches_filter(text):
                row.grid()
            else:
                row.grid_remove()
        for row in self._apps_rows:
            if not text or row.matches_filter(text):
                row.grid()
            else:
                row.grid_remove()
        for row in self._all_rows:
            if not text or row.matches_filter(text):
                row.grid()
            else:
                row.grid_remove()

    def _rebuild_active_tab(self):
        """Rebuild the Active tab from current _toggled_apps."""
        for row in self._active_rows:
            row.destroy()
        self._active_rows.clear()

        if not self._toggled_apps:
            self._active_empty.grid(row=0, column=0, pady=20)
            return

        self._active_empty.grid_forget()

        # Try to reuse app names/icons from existing rows in other tabs
        known = {}
        for row in self._apps_rows + self._all_rows:
            known[row.exe_path] = row

        sorted_paths = sorted(self._toggled_apps.keys(),
                              key=lambda p: os.path.basename(p).lower())
        for i, exe_path in enumerate(sorted_paths):
            # Get name and icon from existing rows if available (no re-extraction)
            existing = known.get(exe_path)
            if existing:
                app_name = existing.app_name
                icon = existing._icon_image
            else:
                app_name = os.path.splitext(os.path.basename(exe_path))[0]
                icon = extract_icon(exe_path)

            row = AppRow(
                self._active_scroll,
                app_name=app_name,
                exe_path=exe_path,
                icon_image=icon,
                default_icon=self._default_icon,
                mode=self._mode,
                initial_state=True,
                on_toggle=self._handle_toggle,
            )
            row.grid(row=i, column=0, sticky="ew", pady=1)
            self._active_rows.append(row)

        self._apply_filter()

    def _sort_rows_toggled_first(self, rows, parent):
        """Re-grid rows so toggled ones appear first, alphabetical within each group."""
        toggled = [r for r in rows if r.exe_path in self._toggled_apps]
        untoggled = [r for r in rows if r.exe_path not in self._toggled_apps]
        toggled.sort(key=lambda r: r.app_name.lower())
        untoggled.sort(key=lambda r: r.app_name.lower())
        sorted_rows = toggled + untoggled
        for r in rows:
            r.grid_forget()
        for i, r in enumerate(sorted_rows):
            r.grid(row=i, column=0, sticky="ew", pady=1)
        rows.clear()
        rows.extend(sorted_rows)

    def _notify_toggled_count(self):
        """Notify the callback with the current toggled count."""
        if self._on_toggled_count_change:
            self._on_toggled_count_change(len(self._toggled_apps))
