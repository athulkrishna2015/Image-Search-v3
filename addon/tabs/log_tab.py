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
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    Qt,
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

    def __init__(self, config: dict, on_dirty, parent=None):
        super().__init__(config, on_dirty, parent)
        self._loaded = False
        self._loading = False
        self._last_mtime = None  # mtime of the log file at last refresh
        self._live = True        # live-update toggle

        # ==== All controls at the top ====
        # 1) Path row
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Log file:"))
        self.path_label = QLabel(self._safe_display_path(), self)
        self.path_label.setTextInteractionFlags(
            self.path_label.textInteractionFlags()
            | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        path_row.addWidget(self.path_label, 1)
        self.body.addLayout(path_row)

        # 2) Verbosity group
        verbosity = QGroupBox("Verbosity", self)
        v_layout = QVBoxLayout(verbosity)
        self.debug_chk = QCheckBox(
            "Log debug (maximum verbosity, off by default)", verbosity
        )
        self.debug_chk.setToolTip(
            "When on, the add-on logs at the 'all' level (everything). "
            "The log file is rotated at 512 KiB so disk usage stays bounded."
        )
        self.debug_chk.setChecked(bool(self.config.get(_DEBUG_KEY, False)))
        self.debug_chk.toggled.connect(self._on_debug_toggled)
        v_layout.addWidget(self.debug_chk)

        level_row = QHBoxLayout()
        level_row.addWidget(QLabel("Log level:"))
        self.level_combo = QComboBox(verbosity)
        for label, value in _LEVELS:
            self.level_combo.addItem(label, value)
        cur_level = (self.config.get("log_level") or log.get_level()).lower()
        for i in range(self.level_combo.count()):
            if self.level_combo.itemData(i) == cur_level:
                self.level_combo.setCurrentIndex(i)
                break
        self.level_combo.currentIndexChanged.connect(self._on_level_changed)
        level_row.addWidget(self.level_combo)
        level_row.addStretch()
        v_layout.addLayout(level_row)
        self.body.addWidget(verbosity)

        # 3) Maintenance group
        maintenance = QGroupBox("Maintenance", self)
        m_layout = QVBoxLayout(maintenance)
        self.clear_on_startup_chk = QCheckBox(
            "Clear log on add-on startup (default)", maintenance
        )
        self.clear_on_startup_chk.setToolTip(
            "When enabled, the log file is truncated every time the add-on "
            "is loaded. Disable to keep a longer history across restarts."
        )
        self.clear_on_startup_chk.setChecked(
            bool(self.config.get(_CLEAR_ON_STARTUP_KEY, True))
        )
        self.clear_on_startup_chk.toggled.connect(self._on_clear_on_startup_toggled)
        m_layout.addWidget(self.clear_on_startup_chk)
        self.body.addWidget(maintenance)

        # 4) Buttons row (right above the text area, all controls together)
        buttons = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh", self)
        self.refresh_btn.setToolTip("Reload the log file from disk.")
        self.refresh_btn.clicked.connect(self._refresh_text)
        self.check_btn = QPushButton("Check log file", self)
        self.check_btn.setToolTip(
            "Scan the log for known error patterns (tracebacks, timeouts, "
            "permission errors, provider failures, etc.) and show a summary."
        )
        self.check_btn.clicked.connect(self._check_log_file)
        self.clear_btn = QPushButton("Clear log", self)
        self.clear_btn.clicked.connect(self._clear_log)
        self.copy_btn = QPushButton("Copy to clipboard", self)
        self.copy_btn.clicked.connect(self._copy_text)
        self.open_btn = QPushButton("Open folder", self)
        self.open_btn.clicked.connect(self._open_folder)
        self.export_btn = QPushButton("Export…", self)
        self.export_btn.clicked.connect(self._export)

        for btn in (
            self.refresh_btn,
            self.check_btn,
            self.clear_btn,
            self.copy_btn,
            self.open_btn,
            self.export_btn,
        ):
            buttons.addWidget(btn)
        buttons.addStretch()
        self.body.addLayout(buttons)

        # Live-update toggle
        self.live_chk = QCheckBox("Live update (auto-refresh as new lines are logged)", self)
        self.live_chk.setChecked(True)
        self.live_chk.toggled.connect(self._on_live_toggled)
        self.body.addWidget(self.live_chk)

        # Findings label (populated by "Check log file")
        self.findings_label = QLabel("", self)
        self.findings_label.setWordWrap(True)
        self.findings_label.setStyleSheet("color: #444;")
        self.findings_label.setTextInteractionFlags(
            self.findings_label.textInteractionFlags()
            | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.body.addWidget(self.findings_label)

        # Help line
        help_label = QLabel(
            "Logs are rotated at 512 KiB x 3. The text area auto-refreshes "
            "when 'Live update' is on; click Refresh to force a reload. "
            "Click 'Check log file' to scan for known error patterns."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #666;")
        self.body.addWidget(help_label)

        # ==== Text area at the bottom, takes all remaining space ====
        self.text = QPlainTextEdit(self)
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.text.setPlaceholderText(
            "(click Refresh to load the log; logs are not loaded automatically)"
        )
        # Make the text area the dominant widget so the user has plenty
        # of room to read logs.
        self.body.addWidget(self.text, 1)

        # Live-update timer: cheap mtime poll.
        self._timer = QTimer(self)
        self._timer.setInterval(_LIVE_TICK_MS)
        self._timer.timeout.connect(self._on_live_tick)
        # Only start when the tab is shown.
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
        # We don't want to overwrite text the user is currently
        # scrolling/selecting in, so we only append new content when
        # the file grew, and replace everything when it shrank (clear).
        path = log.log_path()
        try:
            size = os.path.getsize(path)
            mtime = os.path.getmtime(path)
        except OSError:
            self.text.setPlainText("")
            self._last_mtime = None
            return

        prev_size = self._last_size if hasattr(self, "_last_size") else -1
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
                    cursor = self.text.textCursor()
                    at_end = (
                        cursor.atEnd()
                        or self.text.toPlainText() == ""
                    )
                    self.text.moveCursor(self.text.textCursor().End)
                    self.text.insertPlainText(new.decode("utf-8", errors="replace"))
                    if at_end:
                        self.text.moveCursor(self.text.textCursor().End)
            except OSError:
                pass

        self._last_size = size
        self._last_mtime = mtime

    def _check_log_file(self):
        report = log.check_log_file()
        if not report.get("exists"):
            self.findings_label.setText("Log file does not exist yet.")
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
            self.findings_label.setText(
                f"{header}\nNo known error patterns found."
            )
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
        self.findings_label.setText("\n".join(lines))

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
            if hasattr(self, "_last_size"):
                self._last_size = -1
            self._last_mtime = None
            self._refresh_text()
            self.findings_label.setText("Log cleared.")

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
