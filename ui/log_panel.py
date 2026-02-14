"""
Log panel — collapsible real-time log viewer with a custom logging handler.
"""

import logging
import customtkinter as ctk

MAX_LOG_LINES = 500


class _UILogHandler(logging.Handler):
    """Logging handler that pushes records to a LogPanel widget."""

    def __init__(self, log_panel):
        super().__init__()
        self._panel = log_panel

    def emit(self, record):
        try:
            msg = self.format(record)
            self._panel.after(0, self._panel.append_line, msg)
        except Exception:
            self.handleError(record)


class LogPanel(ctk.CTkFrame):
    """
    Collapsible log panel showing real-time engine activity.
    Sits between the app list and the status bar.
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._visible = False
        self._line_count = 0

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._textbox = ctk.CTkTextbox(
            self,
            font=("Consolas", 12),
            fg_color="#1a1a1a",
            text_color="#cccccc",
            height=180,
            state="disabled",
            wrap="word",
        )
        self._textbox.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Start hidden
        self.grid_remove()

    def toggle(self):
        """Show or hide the log panel. Returns new visibility state."""
        if self._visible:
            self.grid_remove()
            self._visible = False
        else:
            self.grid()
            self._visible = True
        return self._visible

    @property
    def visible(self):
        return self._visible

    def append_line(self, text):
        """Append a log line to the textbox (must be called from main thread)."""
        self._textbox.configure(state="normal")
        if self._line_count > 0:
            self._textbox.insert("end", "\n")
        self._textbox.insert("end", text)
        self._line_count += 1

        # Trim old lines if over the cap
        if self._line_count > MAX_LOG_LINES:
            excess = self._line_count - MAX_LOG_LINES
            self._textbox.delete("1.0", f"{excess + 1}.0")
            self._line_count = MAX_LOG_LINES

        self._textbox.configure(state="disabled")
        self._textbox.see("end")

    def create_handler(self):
        """Create and return a logging.Handler that feeds into this panel."""
        handler = _UILogHandler(self)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s",
                              datefmt="%H:%M:%S")
        )
        return handler
