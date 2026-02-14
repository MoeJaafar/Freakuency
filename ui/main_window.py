"""
Main window — top-level layout assembling all UI frames.
"""

import os
import sys
import webbrowser
import tkinter as tk
from tkinter import messagebox, filedialog

import customtkinter as ctk

from ui.config_frame import ConfigFrame
from ui.app_list_frame import AppListFrame
from ui.log_panel import LogPanel
from ui.status_bar import StatusBar
from ui.popup_menu import PopupMenu

_APP_NAME = "Freakuency"
_VERSION = "0.2.0-alpha"
_GITHUB_URL = "https://github.com/MoeJaafar/Freakuency"
_STARTUP_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


class MainWindow(ctk.CTk):
    """
    Top-level application window.

    Layout:
        [Menu Bar]         — File, View, Help
        [ConfigFrame]      — branding, start/stop, status, mode toggle
        [AppListFrame]     — tabbed app list (Active / Apps / All Processes)
        [LogPanel]         — collapsible real-time log viewer
        [StatusBar]        — split tunnel statistics + log toggle button
    """

    def __init__(self, on_start=None, on_stop=None,
                 on_mode_change=None, on_toggle=None,
                 on_close=None, on_exit=None, default_icon=None,
                 on_export_config=None, on_import_config=None):
        super().__init__()

        self._on_close = on_close      # X button (hide to tray)
        self._on_exit = on_exit        # File > Exit (full quit)
        self._on_export_config = on_export_config
        self._on_import_config = on_import_config

        self.title(f"{_APP_NAME} v{_VERSION}")
        self.geometry("700x800")
        self.minsize(550, 550)

        ctk.set_appearance_mode("dark")
        theme_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "purple_theme.json")
        ctk.set_default_color_theme(theme_path)

        # Window / taskbar icon — use the .ico file
        ico_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "freakuency.ico")
        if os.path.isfile(ico_path):
            self.iconbitmap(ico_path)

        # ── Custom menu bar (dark themed) ──
        self._active_menu = None
        self._build_menu_bar()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)   # App list expands
        self.grid_rowconfigure(3, weight=0)   # Log panel (collapsible)

        # Config frame (top)
        self.config_frame = ConfigFrame(
            self,
            on_start=on_start,
            on_stop=on_stop,
            on_mode_change=on_mode_change,
        )
        self.config_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(10, 5))

        # App list frame (middle, expandable)
        self.app_list = AppListFrame(
            self,
            mode="vpn_default",
            default_icon=default_icon,
            on_toggle=on_toggle,
            on_toggled_count_change=self._on_toggled_count_change,
        )
        self.app_list.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

        # Log panel (between app list and status bar, starts hidden)
        self.log_panel = LogPanel(self)
        self.log_panel.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 0))
        self.log_panel.grid_remove()  # start hidden

        # Status bar (bottom)
        self.status_bar = StatusBar(self, on_log_toggle=self._toggle_log)
        self.status_bar.grid(row=4, column=0, sticky="ew", padx=10, pady=(5, 10))

        # Close handler
        if on_close:
            self.protocol("WM_DELETE_WINDOW", on_close)

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------

    def _build_menu_bar(self):
        self._menu_bar = ctk.CTkFrame(self, height=30, fg_color="#2b2b2b", corner_radius=0)
        self._menu_bar.grid(row=0, column=0, sticky="ew")
        self._menu_bar.grid_columnconfigure(100, weight=1)

        btn_cfg = dict(
            height=28, corner_radius=4,
            fg_color="transparent", hover_color="#3d3d3d",
            text_color="#e0e0e0", font=("", 12),
        )

        self._startup_var = tk.BooleanVar(value=self._is_startup_enabled())
        self._always_on_top_var = tk.BooleanVar(value=False)

        self._file_btn = ctk.CTkButton(self._menu_bar, text="File", width=50, **btn_cfg,
                                       command=lambda: self._show_dropdown(self._file_btn, self._file_items()))
        self._file_btn.grid(row=0, column=0, padx=(4, 0), pady=1)

        self._view_btn = ctk.CTkButton(self._menu_bar, text="View", width=50, **btn_cfg,
                                       command=lambda: self._show_dropdown(self._view_btn, self._view_items()))
        self._view_btn.grid(row=0, column=1, pady=1)

        self._help_btn = ctk.CTkButton(self._menu_bar, text="Help", width=50, **btn_cfg,
                                       command=lambda: self._show_dropdown(self._help_btn, self._help_items()))
        self._help_btn.grid(row=0, column=2, pady=1)

    def _file_items(self):
        return [
            {"label": "Launch on Startup", "command": self._toggle_startup, "checkvar": self._startup_var},
            None,
            {"label": "Export Config...", "command": self._export_config},
            {"label": "Import Config...", "command": self._import_config},
            None,
            {"label": "Exit", "command": self._menu_exit},
        ]

    def _view_items(self):
        return [
            {"label": "Always on Top", "command": self._toggle_always_on_top, "checkvar": self._always_on_top_var},
            {"label": "Toggle Log Panel", "command": self._toggle_log},
            None,
            {"label": "Refresh App List", "command": self._menu_refresh},
        ]

    def _help_items(self):
        return [
            {"label": "GitHub Repository", "command": self._open_github},
            {"label": "Star on GitHub", "command": self._open_github},
            None,
            {"label": "About", "command": self._show_about},
        ]

    def _show_dropdown(self, btn, items):
        """Create and show a PopupMenu below the given button."""
        x = btn.winfo_rootx()
        y = btn.winfo_rooty() + btn.winfo_height() + 2
        menu = PopupMenu(self, items)
        menu.show(x, y)

    # ------------------------------------------------------------------
    # File menu actions
    # ------------------------------------------------------------------

    def _toggle_startup(self):
        """Add or remove Freakuency from Windows startup (current user)."""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, _STARTUP_REG_KEY,
                0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE,
            )
            if self._startup_var.get():
                exe = sys.executable
                # If running as a PyInstaller bundle, use the exe directly
                if getattr(sys, "frozen", False):
                    exe = sys.executable
                else:
                    exe = f'"{sys.executable}" "{os.path.abspath("main.py")}"'
                winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, exe)
            else:
                try:
                    winreg.DeleteValue(key, _APP_NAME)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            messagebox.showerror("Startup Error", f"Could not update startup setting:\n{e}")

    def _is_startup_enabled(self):
        """Check if Freakuency is in the Windows startup registry."""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, _STARTUP_REG_KEY,
                0, winreg.KEY_QUERY_VALUE,
            )
            try:
                winreg.QueryValueEx(key, _APP_NAME)
                winreg.CloseKey(key)
                return True
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False
        except Exception:
            return False

    def _export_config(self):
        path = filedialog.asksaveasfilename(
            title="Export Config",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="freakuency_config.json",
        )
        if not path:
            return
        if self._on_export_config:
            self._on_export_config(path)

    def _import_config(self):
        path = filedialog.askopenfilename(
            title="Import Config",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        if self._on_import_config:
            self._on_import_config(path)

    def _menu_exit(self):
        if self._on_exit:
            self._on_exit()
        elif self._on_close:
            self._on_close()
        else:
            self.destroy()

    # ------------------------------------------------------------------
    # View menu actions
    # ------------------------------------------------------------------

    def _toggle_always_on_top(self):
        self.attributes("-topmost", self._always_on_top_var.get())

    def _menu_refresh(self):
        self.app_list.refresh_apps()

    # ------------------------------------------------------------------
    # Help menu actions
    # ------------------------------------------------------------------

    def _open_github(self):
        webbrowser.open(_GITHUB_URL)

    def _show_about(self):
        """Show a custom-styled About dialog."""
        dlg = ctk.CTkToplevel(self)
        dlg.title(f"About {_APP_NAME}")
        dlg.geometry("400x320")
        dlg.resizable(False, False)
        dlg.attributes("-topmost", True)
        dlg.grab_set()

        # Center on parent
        dlg.update_idletasks()
        px = self.winfo_rootx() + (self.winfo_width() - 400) // 2
        py = self.winfo_rooty() + (self.winfo_height() - 320) // 2
        dlg.geometry(f"+{px}+{py}")

        # Icon path for dialog
        ico_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "freakuency.ico")
        if os.path.isfile(ico_path):
            dlg.after(200, lambda: dlg.iconbitmap(ico_path))

        frame = ctk.CTkFrame(dlg, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=25, pady=20)

        ctk.CTkLabel(
            frame, text=_APP_NAME,
            font=("", 26, "bold"), text_color="#bf5af2",
        ).pack(pady=(5, 0))

        ctk.CTkLabel(
            frame, text=f"v{_VERSION}",
            font=("", 13), text_color="gray",
        ).pack(pady=(2, 10))

        ctk.CTkLabel(
            frame,
            text="Per-app split tunnel manager for Windows.\n"
                 "Route selected applications outside\n"
                 "(or inside) your VPN.",
            font=("", 13), text_color="#e0e0e0", justify="center",
        ).pack(pady=(0, 10))

        ctk.CTkLabel(
            frame, text="Created by MoeJaafar",
            font=("", 12), text_color="#aaaaaa",
        ).pack(pady=(0, 8))

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(pady=(5, 0))

        ctk.CTkButton(
            btn_row, text="GitHub", width=100,
            command=lambda: webbrowser.open(_GITHUB_URL),
            fg_color="#bf5af2", hover_color="#9b3dd6",
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_row, text="Close", width=100,
            command=dlg.destroy,
            fg_color="#555555", hover_color="#666666",
        ).pack(side="left", padx=5)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _toggle_log(self):
        """Toggle the log panel visibility. Returns new state."""
        visible = self.log_panel.toggle()
        if visible:
            self.grid_rowconfigure(3, weight=0, minsize=180)
        else:
            self.grid_rowconfigure(3, weight=0, minsize=0)
        return visible

    def _on_toggled_count_change(self, count):
        """Forward toggled count from app list to config frame."""
        self.config_frame.update_toggled_count(count)
