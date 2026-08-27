# tabs/log_tab.py

from __future__ import annotations

import os
import platform
import subprocess

from aqt.qt import (
    QApplication,
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
    ("Debug (verbose)", "debug"),
    ("Info (default)", "info"),
    ("Warning", "warning"),
    ("Error", "error"),
    ("Critical", "critical"),
]


class LogsTab(TabPage):
    title = "Logs"

    def __init__(self, config: dict, on_dirty, parent=None):
        super().__init__(config, on_dirty, parent)

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

        # Log text area
        self.text = QPlainTextEdit(self)
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.text.setPlaceholderText("(log file is empty)")
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
            "Logs are kept for debugging. Levels above 'Info' are recommended "
            "for normal use; switch to 'Debug' when reporting an issue."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #666;")
        self.body.addWidget(help_label)

        self._refresh_text()

    def _safe_display_path(self) -> str:
        return log.log_path()

    def _on_level_changed(self, *_):
        value = self.level_combo.currentData()
        if value:
            log.set_level(value)
            self.config["log_level"] = value
            self.mark_dirty()
            log.info("log level set to %s", value)

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
