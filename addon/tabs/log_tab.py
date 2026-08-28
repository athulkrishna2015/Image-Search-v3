# tabs/log_tab.py

from __future__ import annotations

import os
import platform
import subprocess

from aqt.qt import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    Qt,
    QTextCursor,
    QTimer,
    QVBoxLayout,
    QWidget,
)

from ..logger import log
from ._base import TabPage


_LEVELS = [
    ("All (very verbose)", "all"),
    ("Debug (verbose)", "debug"),
    ("Info (default)", "info"),
    ("Warning", "warning"),
    ("Error", "error"),
    ("Critical", "critical"),
]

_DEBUG_KEY = "log_debug"
_CLEAR_ON_STARTUP_KEY = "clear_logs_on_startup"

# How often to poll the log file for new content (ms). Cheap; reads the
# mtime only. Real work is only done when the file changed.
_LIVE_TICK_MS = 1500


class LogsTab(TabPage):
    title = "Logs"
    # The log text area scrolls internally; adding an outer
    # QScrollArea would create nested scrolling. The controls above
    # the text area are small enough to fit.
    _scroll_body = False

    def __init__(self, config: dict, on_dirty, parent=None):
        # _scroll_body must be set before TabPage.__init__.
        # TabPage.__init__ reads it on the class, so the class
        # attribute is enough.
        super().__init__(config, on_dirty, parent)
        self._loaded = False
        self._loading = False
        self._last_mtime = None  # mtime of the log file at last refresh
        self._last_size = -1
        self._live = True        # live-update toggle

        # ==== Top: every control in a compact, fixed-height row ====
        # Row 1: file path (single line, read-only)
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("File:"))
        self.path_label = QLabel(self._safe_display_path(), self)
        self.path_label.setTextInteractionFlags(
            self.path_label.textInteractionFlags()
            | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        # Horizontal expansion so the path fills the row.
        self.path_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        path_row.addWidget(self.path_label, 1)
        self.body.addLayout(path_row)

        # Row 2: level (with debug toggle inline), maintenance toggles
        controls_row = QGridLayout()
        controls_row.setContentsMargins(0, 0, 0, 0)
        controls_row.setHorizontalSpacing(12)
        controls_row.setVerticalSpacing(4)

        # Log level
        controls_row.addWidget(QLabel("Level:"), 0, 0)
        self.level_combo = QComboBox()
        for label, value in _LEVELS:
            self.level_combo.addItem(label, value)
        cur_level = (self.config.get("log_level") or log.get_level()).lower()
        for i in range(self.level_combo.count()):
            if self.level_combo.itemData(i) == cur_level:
                self.level_combo.setCurrentIndex(i)
                break
        self.level_combo.currentIndexChanged.connect(self._on_level_changed)
        controls_row.addWidget(self.level_combo, 0, 1)

        # Live update toggle
        self.live_chk = QCheckBox("Live update")
        self.live_chk.setChecked(True)
        self.live_chk.setToolTip(
            "Auto-refresh the log area as new lines are written."
        )
        self.live_chk.toggled.connect(self._on_live_toggled)
        controls_row.addWidget(self.live_chk, 0, 2)

        # Clear on startup toggle
        self.clear_on_startup_chk = QCheckBox("Clear log on add-on startup")
        self.clear_on_startup_chk.setToolTip(
            "Truncate the log file every time the add-on loads. "
            "Disable to keep history across restarts."
        )
        self.clear_on_startup_chk.setChecked(
            bool(self.config.get(_CLEAR_ON_STARTUP_KEY, True))
        )
        self.clear_on_startup_chk.toggled.connect(self._on_clear_on_startup_toggled)
        controls_row.addWidget(self.clear_on_startup_chk, 0, 3)

        # Log debug (maximum verbosity)
        self.debug_chk = QCheckBox("Log debug (max verbosity)")
        self.debug_chk.setToolTip(
            "When on, the add-on logs at the 'all' level. Disk usage is "
            "bounded by 512 KiB rotation."
        )
        self.debug_chk.setChecked(bool(self.config.get(_DEBUG_KEY, False)))
        self.debug_chk.toggled.connect(self._on_debug_toggled)
        controls_row.addWidget(self.debug_chk, 0, 4)

        # Push the columns left so the layout stays compact.
        controls_row.setColumnStretch(0, 0)
        controls_row.setColumnStretch(1, 0)
        controls_row.setColumnStretch(2, 0)
        controls_row.setColumnStretch(3, 0)
        controls_row.setColumnStretch(4, 0)
        # Make a vertical layout wrapper so we can add the grid to body.
        controls_widget = QWidget(self)
        controls_widget.setLayout(controls_row)
        self.body.addWidget(controls_widget)

        # Row 3: action buttons
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(6)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setToolTip("Reload the log file from disk.")
        self.refresh_btn.clicked.connect(self._refresh_text)
        self.check_btn = QPushButton("Check log file")
        self.check_btn.setToolTip(
            "Scan the log for known error patterns (tracebacks, timeouts, "
            "permission errors, provider failures, etc.) and show a summary."
        )
        self.check_btn.clicked.connect(self._check_log_file)
        self.clear_btn = QPushButton("Clear log")
        self.clear_btn.clicked.connect(self._clear_log)
        self.copy_btn = QPushButton("Copy")
        self.copy_btn.clicked.connect(self._copy_text)
        self.open_btn = QPushButton("Open folder")
        self.open_btn.clicked.connect(self._open_folder)
        self.export_btn = QPushButton("Export…")
        self.export_btn.clicked.connect(self._export)

        for btn in (
            self.refresh_btn, self.check_btn, self.clear_btn,
            self.copy_btn, self.open_btn, self.export_btn,
        ):
            buttons_row.addWidget(btn)
        buttons_row.addStretch()
        buttons_widget = QWidget(self)
        buttons_widget.setLayout(buttons_row)
        self.body.addWidget(buttons_widget)

        # Row 4: findings label (compact, only shown after Check log file)
        self.findings_label = QLabel("", self)
        self.findings_label.setWordWrap(True)
        self.findings_label.setStyleSheet("color: #444;")
        self.findings_label.setTextInteractionFlags(
            self.findings_label.textInteractionFlags()
            | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.findings_label.setVisible(False)
        self.body.addWidget(self.findings_label)
        # Track first findings so the label becomes visible.
        self._findings_has_content = False

        # ==== Bottom: the log area, takes all remaining space ====
        self.text = QPlainTextEdit(self)
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.text.setPlaceholderText(
            "(click Refresh to load the log; logs are not loaded automatically)"
        )
        # Crucial: stretch factor of 1 makes this the dominant widget.
        self.body.addWidget(self.text, 1)

        # Optional help line at the very bottom (sits in the bottom
        # of the dialog frame, not inside the log area).
        help_label = QLabel(
            "Tips: enable 'Live update' to follow the log in real time. "
            "Click 'Check log file' to scan for known error patterns. "
            "Switching to this tab auto-loads on first focus.",
            self,
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #666; font-size: 11px;")
        help_label.setVisible(False)  # hidden by default to save space
        self.body.addWidget(help_label)
        self._help_label = help_label

        # Live-update timer: cheap mtime poll. Started lazily on first
        # tab focus so we don't burn cycles when the user never opens
        # the Logs tab.
        self._timer = QTimer(self)
        self._timer.setInterval(_LIVE_TICK_MS)
        self._timer.timeout.connect(self._on_live_tick)
        self.destroyed.connect(self._timer.stop)

    # ---- public API used by the dialog ----
    def load_if_needed(self):
        """Called by the dialog the first time this tab is shown."""
        if self._loaded or self._loading:
            return
        self._loading = True
        try:
            self._refresh_text()
        finally:
            self._loading = False
        self._loaded = True
        if self._live and not self._timer.isActive():
            self._timer.start()

    # ---- internals ----
    def _safe_display_path(self) -> str:
        return log.log_path()

    def _on_level_changed(self, *_):
        value = self.level_combo.currentData()
        if not value:
            return
        log.set_level(value)
        self.config["log_level"] = value
        is_verbose = value in ("all", "debug")
        if self.debug_chk.isChecked() != is_verbose:
            self.debug_chk.blockSignals(True)
            self.debug_chk.setChecked(is_verbose)
            self.debug_chk.blockSignals(False)
        self.config[_DEBUG_KEY] = is_verbose
        self.mark_dirty()
        log.info("log level set to %s", value)

    def _on_debug_toggled(self, checked: bool):
        if checked:
            target = "all"
        else:
            target = (self.config.get("log_level") or "info")
        log.set_level(target)
        self.config[_DEBUG_KEY] = checked
        for i in range(self.level_combo.count()):
            if self.level_combo.itemData(i) == target:
                self.level_combo.blockSignals(True)
                self.level_combo.setCurrentIndex(i)
                self.level_combo.blockSignals(False)
                break
        self.mark_dirty()
        log.info("log debug toggle: %s -> level=%s", checked, target)

    def _on_clear_on_startup_toggled(self, checked: bool):
        self.config[_CLEAR_ON_STARTUP_KEY] = bool(checked)
        self.mark_dirty()
        log.info("clear on startup: %s", checked)

    def _on_live_toggled(self, checked: bool):
        self._live = bool(checked)
        if self._live:
            # Force a refresh immediately so the user sees the latest.
            self._last_mtime = None
            self._last_size = -1
            self._refresh_text()
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()

    def _on_live_tick(self):
        """
        Cheap mtime poll. Only do real work if the log file's mtime
        has changed since the last refresh.
        """
        path = log.log_path()
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return
        if mtime != self._last_mtime:
            self._refresh_text()

    def _refresh_text(self):
        """
        Read the current log file and update the view.
        - On first load or after a Clear (file shrank), do a full reload.
        - On subsequent loads (file grew), read only the new bytes and
          append to the end of the existing text without disturbing
          the user's cursor if they have scrolled up to read history.
        """
        path = log.log_path()
        try:
            size = os.path.getsize(path)
            mtime = os.path.getmtime(path)
        except OSError:
            self.text.setPlainText("")
            self._last_mtime = None
            self._last_size = -1
            return

        prev_size = self._last_size
        if prev_size < 0 or size < prev_size:
            # First load or file shrank (e.g. user clicked Clear).
            self.text.setPlainText(log.tail_text())
        else:
            # File grew: read only the new bytes and append.
            try:
                with open(path, "rb") as fh:
                    fh.seek(prev_size)
                    new = fh.read(size - prev_size)
                if new:
                    # appendPlainText appends to the end and moves the
                    # cursor there. If the user is not at the end (they
                    # scrolled up to read history), we insert at the end
                    # without changing their cursor, then restore the
                    # cursor to its previous position.
                    cursor = self.text.textCursor()
                    was_at_end = cursor.atEnd() or self.text.toPlainText() == ""
                    if was_at_end:
                        # Cursor already at end; just append.
                        self.text.appendPlainText(
                            new.decode("utf-8", errors="replace")
                        )
                    else:
                        # Insert at end, then restore the user's cursor
                        # so their view is preserved.
                        self.text.moveCursor(QTextCursor.MoveOperation.End)
                        self.text.insertPlainText(
                            new.decode("utf-8", errors="replace")
                        )
                        self.text.setTextCursor(cursor)
            except OSError:
                pass

        self._last_size = size
        self._last_mtime = mtime

    def _check_log_file(self):
        report = log.check_log_file()
        if not report.get("exists"):
            self._show_findings("Log file does not exist yet.")
            return

        size_kb = report["size_bytes"] / 1024.0
        note = report.get("checked_bytes_note", "")
        header = (
            f"Scanned {report['checked_bytes']:,} bytes "
            f"({report['line_count']:,} lines) of the {size_kb:.1f} KiB log file."
        )
        if note:
            header += f"\n{note}"

        findings = report.get("findings") or []
        if not findings:
            self._show_findings(f"{header}\nNo known error patterns found.")
            return

        lines = [header, "Findings:"]
        for f in findings:
            lines.append(
                f"  - {f['category']}: {f['count']} occurrence(s) "
                f"(lines {f['first_line_no']}..{f['last_line_no']})"
            )
            if f.get("sample"):
                lines.append(f"      sample: {f['sample']}")
        if "error" in report:
            lines.append(f"Scanner error: {report['error']}")
        self._show_findings("\n".join(lines))

    def _show_findings(self, text: str):
        self.findings_label.setText(text)
        if not self._findings_has_content:
            self.findings_label.setVisible(True)
            self._findings_has_content = True

    def _clear_log(self):
        ret = QMessageBox.question(
            self,
            "Clear log",
            "Erase the current log file? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        if log.clear():
            # Force a full reload (file shrank to zero).
            self._last_size = -1
            self._last_mtime = None
            self._refresh_text()
            self._show_findings("Log cleared.")

    def _copy_text(self):
        QApplication.clipboard().setText(self.text.toPlainText())

    def _open_folder(self):
        path = log.log_dir()
        if not os.path.isdir(path):
            QMessageBox.warning(
                self, "Folder not found", f"Log folder does not exist yet:\n{path}"
            )
            return
        try:
            system = platform.system()
            if system == "Windows":
                os.startfile(path)  # type: ignore[attr-defined]
            elif system == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as exc:
            QMessageBox.warning(
                self, "Could not open folder", f"{path}\n\n{exc}"
            )

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export log",
            "image_search_v3.log",
            "Log files (*.log);;All files (*)",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.text.toPlainText())
        except Exception as exc:
            QMessageBox.warning(
                self, "Could not export", f"{path}\n\n{exc}"
            )
            return
        self.path_label.setText(path)
