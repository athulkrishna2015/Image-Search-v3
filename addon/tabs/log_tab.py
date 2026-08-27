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
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    Qt,
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


class LogsTab(TabPage):
    title = "Logs"

    def __init__(self, config: dict, on_dirty, parent=None):
        super().__init__(config, on_dirty, parent)
        self._loaded = False
        self._loading = False

        # Path row
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Log file:"))
        self.path_label = QLabel(self._safe_display_path(), self)
        self.path_label.setTextInteractionFlags(
            self.path_label.textInteractionFlags()
            | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        path_row.addWidget(self.path_label, 1)
        self.body.addLayout(path_row)

        # Quick toggle: enable maximum logging without picking a level.
        self.debug_chk = QCheckBox(
            "Log debug (maximum verbosity, off by default)", self
        )
        self.debug_chk.setToolTip(
            "When on, the add-on logs at the 'all' level (everything). "
            "The log file is rotated at 512 KiB so disk usage stays bounded."
        )
        self.debug_chk.setChecked(bool(self.config.get(_DEBUG_KEY, False)))
        self.debug_chk.toggled.connect(self._on_debug_toggled)
        self.body.addWidget(self.debug_chk)

        # Log level row
        level_row = QHBoxLayout()
        level_row.addWidget(QLabel("Log level:"))
        self.level_combo = QComboBox(self)
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
        self.body.addLayout(level_row)

        # Log text area. Placeholder text is shown until the user actually
        # asks to load it; this keeps dialog open instant even for large
        # rotated logs.
        self.text = QPlainTextEdit(self)
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.text.setPlaceholderText(
            "(click Refresh to load the log; logs are not loaded automatically)"
        )
        self.body.addWidget(self.text, 1)

        # Buttons row
        buttons = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh", self)
        self.refresh_btn.clicked.connect(self._refresh_text)
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
            self.clear_btn,
            self.copy_btn,
            self.open_btn,
            self.export_btn,
        ):
            buttons.addWidget(btn)
        buttons.addStretch()
        self.body.addLayout(buttons)

        # Help
        help_label = QLabel(
            "Logs are rotated at 512 KiB x 3. The log viewer is lazy: nothing "
            "is read from disk until you click Refresh. To capture a bug, "
            "tick 'Log debug' and reproduce the issue, then Refresh."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #666;")
        self.body.addWidget(help_label)

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

    # ---- internals ----
    def _safe_display_path(self) -> str:
        return log.log_path()

    def _on_level_changed(self, *_):
        value = self.level_combo.currentData()
        if not value:
            return
        log.set_level(value)
        self.config["log_level"] = value
        # If the user manually changes the level, the "log debug" toggle
        # becomes a representation of "is level <= debug?"; uncheck it
        # if they pick a less verbose level.
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
            # Restore the previously configured level (or the current logger
            # level if no preference is set).
            target = (self.config.get("log_level") or "info")
        log.set_level(target)
        self.config[_DEBUG_KEY] = checked
        # Sync the combo without re-emitting the change handler.
        for i in range(self.level_combo.count()):
            if self.level_combo.itemData(i) == target:
                self.level_combo.blockSignals(True)
                self.level_combo.setCurrentIndex(i)
                self.level_combo.blockSignals(False)
                break
        self.mark_dirty()
        log.info("log debug toggle: %s -> level=%s", checked, target)

    def _refresh_text(self):
        self.text.setPlainText(log.tail_text())

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
            self._refresh_text()

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
