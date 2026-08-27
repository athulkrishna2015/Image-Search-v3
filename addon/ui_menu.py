from __future__ import annotations

from aqt import mw
from aqt.utils import qconnect
from aqt.qt import (
    QAction,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTabWidget,
    QVBoxLayout,
)

from . import utils
from .logger import log
from .tabs import LogsTab, NetworkTab, NoteTypesTab, SupportTab

_MENU_INSTALLED = False
_MW_MENU_FLAG = "_imgsearchv3_menu_installed"


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Search v3 Settings")
        self.setMinimumWidth(720)

        self.config = utils.get_config() or {}
        self.status_label = QLabel("", self)
        self.status_label.setStyleSheet("color: #2e7d32;")

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs)

        # Per-tab dirty flag, set via self._mark_dirty.
        self._any_dirty = False

        self.nt_tab = NoteTypesTab(self.config, on_dirty=self._mark_dirty, parent=self)
        self.net_tab = NetworkTab(self.config, on_dirty=self._mark_dirty, parent=self)
        self.log_tab = LogsTab(self.config, on_dirty=self._mark_dirty, parent=self)
        self.support_tab = SupportTab(self.config, on_dirty=self._mark_dirty, parent=self)

        self.tabs.addTab(self.nt_tab, self.nt_tab.title)
        self.tabs.addTab(self.net_tab, self.net_tab.title)
        self.tabs.addTab(self.log_tab, self.log_tab.title)
        self.tabs.addTab(self.support_tab, self.support_tab.title)

        # Switch to the Logs tab when config has a fresh warning; otherwise
        # start on Note Types.
        self.tabs.setCurrentWidget(self.nt_tab)

        layout.addWidget(self.status_label)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        save_btn = button_box.button(QDialogButtonBox.StandardButton.Save)
        save_btn.clicked.connect(self._save_only)
        save_close_btn = button_box.addButton(
            "Save and Close", QDialogButtonBox.ButtonRole.AcceptRole
        )
        save_close_btn.clicked.connect(self._save_and_close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _mark_dirty(self):
        self._any_dirty = True
        if self.status_label.text():
            self.status_label.setText("")

    def _clear_status(self):
        self.status_label.setText("")

    def _save_only(self):
        # Pull everything from each tab into self.config, then persist.
        if self.nt_tab.is_dirty():
            self.nt_tab.save_current()

        net = self.net_tab.collect()
        for key, value in net.items():
            self.config[key] = value

        # log_level is already mutated in-place by the Logs tab.

        # Strip legacy keys.
        for legacy in ("query_field", "query_fields", "image_field", "search_engine"):
            self.config.pop(legacy, None)

        try:
            mw.addonManager.writeConfig(__name__, self.config)
            self.status_label.setText("Saved.")
            self.nt_tab.clear_dirty()
            self._any_dirty = False
        except Exception as exc:
            log.error("Settings save failed: %r", exc)
            self.status_label.setText("Could not save settings.")

    def _save_and_close(self):
        self._save_only()
        self.accept()


def settings_dialog():
    dlg = SettingsDialog(mw)
    dlg.exec()


def init_menu():
    global _MENU_INSTALLED
    if _MENU_INSTALLED or (mw and getattr(mw, _MW_MENU_FLAG, False)):
        return
    if not mw or not hasattr(mw, "form"):
        return
    for existing in mw.form.menuTools.actions():
        if existing.objectName() == "imgsearchv3_settings_action":
            _MENU_INSTALLED = True
            if mw:
                setattr(mw, _MW_MENU_FLAG, True)
            return
    action = QAction("Image Search v3 Settings", mw)
    action.setObjectName("imgsearchv3_settings_action")
    qconnect(action.triggered, settings_dialog)
    mw.form.menuTools.addAction(action)
    _MENU_INSTALLED = True
    if mw:
        setattr(mw, _MW_MENU_FLAG, True)
