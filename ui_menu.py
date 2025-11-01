from aqt import mw
from aqt.utils import qconnect
from aqt.qt import *
import json

from . import utils

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Search v3 Settings")
        self.setMinimumWidth(700)

        self.config = utils.get_config()
        self.note_types = mw.col.models.all()
        self.dirty = False  # tracks if anything in dialog changed

        # --- Dialog Layout ---
        v_layout = QVBoxLayout(self)

        # Tabs
        self.tabs = QTabWidget()
        v_layout.addWidget(self.tabs)

        # Tab 1: Note Types (per-model settings)
        self.nt_tab = QWidget()
        self.tabs.addTab(self.nt_tab, "Note Types")
        nt_layout = QHBoxLayout(self.nt_tab)

        # Left side: note types list
        self.note_types_list = QListWidget()
        self.note_types_list.addItems([nt["name"] for nt in self.note_types])
        self.note_types_list.currentItemChanged.connect(self.on_note_type_selected)
        nt_layout.addWidget(self.note_types_list, 1)

        # Right side: settings for selected note type
        right_side = QWidget()
        self.right_layout = QVBoxLayout(right_side)
        nt_layout.addWidget(right_side, 2)

        self.right_layout.addWidget(QLabel("Settings for selected note type:"))

        # Query fields selector
        self.right_layout.addWidget(QLabel("Query Fields (for searching):"))
        self.query_fields_list = QListWidget()
        self.query_fields_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.query_fields_list.itemSelectionChanged.connect(self.mark_dirty)
        self.right_layout.addWidget(self.query_fields_list)

        # Image field selector
        self.right_layout.addWidget(QLabel("Image Field (for placing image):"))
        self.image_field_combo = QComboBox()
        self.image_field_combo.currentIndexChanged.connect(self.mark_dirty)
        self.right_layout.addWidget(self.image_field_combo)

        # Image placement selector
        self.right_layout.addWidget(QLabel("Image Placement:"))
        self.placement_combo = QComboBox()
        # 'replace' is the default
        self.placement_combo.addItem("Replace field content", "replace")
        self.placement_combo.addItem("Append to field", "append")
        self.placement_combo.addItem("Prepend to field", "prepend")
        self.placement_combo.currentIndexChanged.connect(self.mark_dirty)
        self.right_layout.addWidget(self.placement_combo)

        # Reset per-note-type defaults
        nt_buttons_row = QHBoxLayout()
        self.reset_nt_button = QPushButton("Reset Note-Type Defaults")
        self.reset_nt_button.clicked.connect(self.reset_nt_to_default)
        nt_buttons_row.addWidget(self.reset_nt_button)
        nt_buttons_row.addStretch()
        self.right_layout.addLayout(nt_buttons_row)

        # Tab 2: Network (global)
        self.net_tab = QWidget()
        self.tabs.addTab(self.net_tab, "Network")
        net_v = QVBoxLayout(self.net_tab)

        net_group = QGroupBox("Yandex request settings")
        net_form = QFormLayout(net_group)

        self.timeout_spin = QDoubleSpinBox()
        self.timeout_spin.setRange(1.0, 120.0)
        self.timeout_spin.setSingleStep(0.25)
        self.timeout_spin.setDecimals(2)
        self.timeout_spin.setValue(float(self.config.get("request_timeout_s", 10.0)))
        self.timeout_spin.valueChanged.connect(self.mark_dirty)
        net_form.addRow("Request timeout (s):", self.timeout_spin)

        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(0, 10)
        self.retries_spin.setValue(int(self.config.get("max_retries", 5)))
        self.retries_spin.valueChanged.connect(self.mark_dirty)
        net_form.addRow("Max retries:", self.retries_spin)

        self.backoff_spin = QDoubleSpinBox()
        self.backoff_spin.setRange(0.05, 10.0)
        self.backoff_spin.setSingleStep(0.05)
        self.backoff_spin.setDecimals(2)
        self.backoff_spin.setValue(float(self.config.get("backoff_base_s", 0.75)))
        self.backoff_spin.valueChanged.connect(self.mark_dirty)
        net_form.addRow("Backoff base (s):", self.backoff_spin)

        net_v.addWidget(net_group)

        net_buttons_row = QHBoxLayout()
        self.reset_net_button = QPushButton("Reset Network Defaults")
        self.reset_net_button.clicked.connect(self.reset_net_to_default)
        net_buttons_row.addWidget(self.reset_net_button)
        net_buttons_row.addStretch()
        net_v.addLayout(net_buttons_row)

        # Inline status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #2e7d32;")
        v_layout.addWidget(self.status_label)

        # Dialog buttons (bottom)
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        # Save should NOT close dialog
        save_btn = button_box.button(QDialogButtonBox.StandardButton.Save)
        save_btn.clicked.connect(self.save_only)
        button_box.rejected.connect(self.reject)
        v_layout.addWidget(button_box)

        # Initialize first note type selection
        if self.note_types:
            self.note_types_list.setCurrentRow(0)

    # --- Note-type tab logic ---

    def on_note_type_selected(self, current, previous):
        if self.dirty and previous:
            ret = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes for '{}'. Do you want to save them before switching?".format(previous.text()),
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if ret == QMessageBox.StandardButton.Save:
                self.save_note_type_config(self.note_types[self.note_types_list.row(previous)])
            elif ret == QMessageBox.StandardButton.Cancel:
                self.note_types_list.setCurrentItem(previous)
                return

        if not current:
            return

        self.load_note_type_config(self.note_types[self.note_types_list.row(current)])
        self.dirty = False
        self.status_label.setText("")

    def load_note_type_config(self, note_type):
        # Block signals to prevent dirty flag
        self.query_fields_list.blockSignals(True)
        self.image_field_combo.blockSignals(True)
        self.placement_combo.blockSignals(True)

        field_names = [f["name"] for f in note_type["flds"]]
        nt_id = str(note_type["id"])

        # Populate field lists
        self.query_fields_list.clear()
        self.query_fields_list.addItems(field_names)
        self.image_field_combo.clear()
        self.image_field_combo.addItems(field_names)

        # Get config for this note type
        configs = self.config.setdefault("configs_by_notetype_id", {})
        nt_config = configs.get(nt_id)

        if nt_config:
            # Load saved settings
            selected_query_fields = nt_config.get("query_fields", [])
            for i in range(self.query_fields_list.count()):
                item = self.query_fields_list.item(i)
                if item.text() in selected_query_fields:
                    item.setSelected(True)

            image_field = nt_config.get("image_field")
            if image_field in field_names:
                self.image_field_combo.setCurrentText(image_field)
            else:
                if self.image_field_combo.count() > 0:
                    self.image_field_combo.setCurrentIndex(self.image_field_combo.count() - 1)

            placement = nt_config.get("image_placement", "replace")
            index = self.placement_combo.findData(placement)
            if index != -1:
                self.placement_combo.setCurrentIndex(index)
        else:
            # Defaults: first field for query, last field for image, placement='replace'
            if self.query_fields_list.count() > 0:
                self.query_fields_list.item(0).setSelected(True)
            if self.image_field_combo.count() > 0:
                self.image_field_combo.setCurrentIndex(self.image_field_combo.count() - 1)
            self.placement_combo.setCurrentIndex(0)

        # Unblock signals
        self.query_fields_list.blockSignals(False)
        self.image_field_combo.blockSignals(False)
        self.placement_combo.blockSignals(False)

    def save_note_type_config(self, note_type):
        nt_id = str(note_type["id"])
        configs = self.config.setdefault("configs_by_notetype_id", {})

        selected_query_items = self.query_fields_list.selectedItems()
        query_fields = [item.text() for item in selected_query_items]
        image_field = self.image_field_combo.currentText()
        placement = self.placement_combo.currentData()

        configs[nt_id] = {
            "query_fields": query_fields,
            "image_field": image_field,
            "image_placement": placement,
        }

        self.dirty = False

    # --- Network tab helpers ---

    def reset_net_to_default(self):
        self.timeout_spin.setValue(10.0)
        self.retries_spin.setValue(5)
        self.backoff_spin.setValue(0.75)
        self.mark_dirty()

    def reset_nt_to_default(self):
        current_row = self.note_types_list.currentRow()
        if current_row < 0:
            return

        # Temporarily block to avoid spurious dirty
        self.query_fields_list.blockSignals(True)
        self.image_field_combo.blockSignals(True)
        self.placement_combo.blockSignals(True)

        self.query_fields_list.clearSelection()
        if self.query_fields_list.count() > 0:
            self.query_fields_list.item(0).setSelected(True)
        if self.image_field_combo.count() > 0:
            self.image_field_combo.setCurrentIndex(self.image_field_combo.count() - 1)
        self.placement_combo.setCurrentIndex(0)  # 'replace'

        self.query_fields_list.blockSignals(False)
        self.image_field_combo.blockSignals(False)
        self.placement_combo.blockSignals(False)

        self.mark_dirty()

    # --- Common ---

    def mark_dirty(self, *args):
        self.dirty = True
        self.status_label.setText("")

    def save_only(self):
        # Save per-note-type settings for the currently selected model
        current_row = self.note_types_list.currentRow()
        if current_row >= 0:
            self.save_note_type_config(self.note_types[current_row])

        # Save global network settings
        self.config["request_timeout_s"] = float(self.timeout_spin.value())
        self.config["max_retries"] = int(self.retries_spin.value())
        self.config["backoff_base_s"] = float(self.backoff_spin.value())

        # Clean up old root-level config keys for consistency
        self.config.pop("query_fields", None)
        self.config.pop("query_field", None)
        self.config.pop("image_field", None)
        self.config.pop("search_engine", None)

        mw.addonManager.writeConfig(__name__, self.config)

        # Inline feedback
        self.status_label.setText("Saved")
        self.dirty = False


def settings_dialog():
    dialog = SettingsDialog(mw)
    dialog.exec()


def init_menu():
    action = QAction("Image Search v3 Settings", mw)
    qconnect(action.triggered, settings_dialog)
    mw.form.menuTools.addAction(action)
