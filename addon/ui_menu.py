from __future__ import annotations

from aqt import mw
from aqt.utils import qconnect
from aqt.qt import (
    QAction,
    QCloseEvent,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTabWidget,
    QVBoxLayout,
    Qt,
)

from . import update_check
from . import utils
from .logger import log
from .tabs import (
    ADDON_PACKAGE,
    LogsTab,
    NetworkTab,
    NoteTypesTab,
    SupportTabMixin,
)

_MENU_INSTALLED = False
_MW_MENU_FLAG = "_imgsearchv3_menu_installed"

# Single live dialog instance so re-opening the menu focuses the existing
# window instead of stacking a new one.
_DIALOG_INST: SettingsDialog | None = None


class SettingsDialog(QDialog, SupportTabMixin):
    """
    Settings dialog for Image Search v3. Composes per-tab widgets under
    `addon/tabs/`, with the Support tab contributed by `SupportTabMixin`.
    The auto-pop on update happens lazily here, when the user opens the
    dialog, so Anki startup is not affected.

    The dialog is **non-modal**: opening it does not block the Anki
    main window. The user can keep editing cards while the settings
    are open. We use `show()` rather than `exec()`.
    """

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        SupportTabMixin.__init__(self)

        # Top-level window (not a child of mw) so the user can keep
        # working in Anki while the settings dialog is open.
        self.setWindowTitle("Image Search v3 Settings")
        self.setMinimumWidth(720)
        # On macOS this is the default but be explicit.
        self.setWindowModality(Qt.WindowModality.NonModal)

        self.config = utils.get_config() or {}
        self._any_dirty = False

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs)

        self.status_label = QLabel("", self)
        self.status_label.setStyleSheet("color: #2e7d32;")
        self._build_tabs()

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
        button_box.rejected.connect(self._on_cancel)
        layout.addWidget(button_box)

        self._maybe_focus_support_tab()

    # ---- Qt overrides ----
    def closeEvent(self, event: QCloseEvent):
        """Treat the window's close button the same as Cancel."""
        self._on_cancel()
        event.accept()

    # ---- tab assembly ----
    def _build_tabs(self):
        self.nt_tab = NoteTypesTab(self.config, on_dirty=self._mark_dirty, parent=self)
        self.net_tab = NetworkTab(self.config, on_dirty=self._mark_dirty, parent=self)
        # Support tab is built by the mixin; it uses mw.addonManager.addonMeta
        # so the supporter-opt-out checkbox is wired in.
        self.support_tab = self._create_support_tab()
        # Logs is the LAST tab on purpose. The log viewer is lazy (no disk
        # read until Refresh is clicked) so it does not slow dialog open.
        self.log_tab = LogsTab(self.config, on_dirty=self._mark_dirty, parent=self)

        self.tabs.addTab(self.nt_tab, self.nt_tab.title)
        self.tabs.addTab(self.net_tab, self.net_tab.title)
        self.tabs.addTab(self.support_tab, "Support")
        self.tabs.addTab(self.log_tab, self.log_tab.title)
        self.tabs.setCurrentWidget(self.nt_tab)
        # Lazy-load the log when the user actually focuses the Logs tab.
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index: int):
        if self.tabs.widget(index) is self.log_tab:
            self.log_tab.load_if_needed()

    def _maybe_focus_support_tab(self):
        """
        If the add-on was updated since the user was last welcomed, switch
        to the Support tab on dialog open. This runs only on dialog
        construction (user-initiated), never at add-on import.
        """
        try:
            if update_check.should_show_support_welcome(self.config):
                self.tabs.setCurrentWidget(self.support_tab)
                update_check.mark_support_welcomed()
                log.info("auto-showed Support tab (post-update welcome)")
        except Exception as exc:
            log.warning("auto-show support tab failed: %r", exc)

    # ---- dirty / save ----
    def _mark_dirty(self):
        self._any_dirty = True
        if self.status_label.text():
            self.status_label.setText("")

    def _save_only(self):
        if self.nt_tab.is_dirty():
            self.nt_tab.save_current()

        net = self.net_tab.collect()
        for key, value in net.items():
            self.config[key] = value

        # The Logs tab mutates config['log_level'] / 'log_debug' /
        # 'clear_logs_on_startup' / 'check_log_file' in place; nothing
        # extra to do here.

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
        self._hide()

    def _on_cancel(self):
        # Discard unsaved changes for the per-note-type tab (the only
        # tab with a per-instance dirty flag). Network/Logs/Support
        # mutate the shared config dict, so we don't undo those.
        if self.nt_tab.is_dirty():
            # Re-read the on-disk config to refresh tab state.
            self.config = utils.get_config() or {}
            # The simplest way to undo per-note-type changes is to
            # rebuild the tab from the on-disk config. But the other
            # tabs already mirror the in-memory config; instead we
            # just clear the dirty flag and leave the UI as-is so
            # the user can see what they had, while not persisting.
            self.nt_tab.clear_dirty()
        self._hide()

    def _hide(self):
        global _DIALOG_INST
        self.hide()
        if _DIALOG_INST is self:
            _DIALOG_INST = None
        self.deleteLater()


def settings_dialog():
    """
    Show (or focus) the settings dialog. Non-modal: the user can keep
    editing in Anki while the dialog is open.
    """
    global _DIALOG_INST
    if _DIALOG_INST is not None:
        try:
            # If the user closed the window from the X button, the
            # C++ side is gone but the Python wrapper may still exist.
            _DIALOG_INST.show()
            _DIALOG_INST.raise_()
            _DIALOG_INST.activateWindow()
            return
        except RuntimeError:
            _DIALOG_INST = None

    _DIALOG_INST = SettingsDialog(None)  # top-level window
    _DIALOG_INST.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    _DIALOG_INST.show()


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


__all__ = ["SettingsDialog", "settings_dialog", "init_menu", "ADDON_PACKAGE"]
