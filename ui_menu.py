from aqt import mw
from aqt.utils import qconnect
from aqt.qt import *
import json

from . import utils

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Search v3 Settings")
        self.setMinimumWidth(600)

        self.config = utils.get_config()
        self.note_types = mw.col.models.all()
        self.dirty = False

        # --- Main Layout --- #
        v_layout = QVBoxLayout(self)

        

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        v_layout.addWidget(line)

        # --- Per-Note-Type Layout --- #
        main_layout = QHBoxLayout()
        v_layout.addLayout(main_layout)

        # Left side: Note types list
        self.note_types_list = QListWidget()
        self.note_types_list.addItems([nt['name'] for nt in self.note_types])
        self.note_types_list.currentItemChanged.connect(self.on_note_type_selected)
        main_layout.addWidget(self.note_types_list)

        # Right side: Settings for the selected note type
        right_side = QWidget()
        self.right_layout = QVBoxLayout(right_side)
        main_layout.addWidget(right_side)

        self.right_layout.addWidget(QLabel("<b>Settings for selected note type:</b>"))

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
        self.placement_combo.addItem("Replace field content", "replace")
        self.placement_combo.addItem("Append to field", "append")
        self.placement_combo.addItem("Prepend to field", "prepend")
        self.placement_combo.currentIndexChanged.connect(self.mark_dirty)
        self.right_layout.addWidget(self.placement_combo)

        # Buttons
        self.reset_button = QPushButton("Reset to Default")
        self.reset_button.clicked.connect(self.reset_to_default)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.save_and_close)
        button_box.rejected.connect(self.reject)

        bottom_buttons_layout = QHBoxLayout()
        bottom_buttons_layout.addWidget(self.reset_button)
        bottom_buttons_layout.addStretch()
        bottom_buttons_layout.addWidget(button_box)
        self.right_layout.addLayout(bottom_buttons_layout)

        # Select the first note type to populate the fields
        if self.note_types:
            self.note_types_list.setCurrentRow(0)

    def on_note_type_selected(self, current, previous):
        if self.dirty:
            if previous:
                ret = QMessageBox.question(self, "Unsaved Changes", 
                                           "You have unsaved changes for '<b>{}</b>'.<br>Do you want to save them before switching?".format(previous.text()),
                                           QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
                if ret == QMessageBox.StandardButton.Save:
                    self.save_note_type_config(self.note_types[self.note_types_list.row(previous)])
                elif ret == QMessageBox.StandardButton.Cancel:
                    self.note_types_list.setCurrentItem(previous)
                    return
        
        if not current:
            return

        self.load_note_type_config(self.note_types[self.note_types_list.row(current)])
        self.dirty = False

    def load_note_type_config(self, note_type):
        # Block signals to prevent dirty flag
        self.query_fields_list.blockSignals(True)
        self.image_field_combo.blockSignals(True)
        self.placement_combo.blockSignals(True)

        field_names = [f['name'] for f in note_type['flds']]
        nt_id = str(note_type['id'])

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
            else: # Saved field no longer exists, apply default
                if self.image_field_combo.count() > 0:
                    self.image_field_combo.setCurrentIndex(self.image_field_combo.count() - 1)
            
            placement = nt_config.get("image_placement", "append")
            index = self.placement_combo.findData(placement)
            if index != -1:
                self.placement_combo.setCurrentIndex(index)

        else:
            # Apply default settings
            if self.query_fields_list.count() > 0:
                self.query_fields_list.item(0).setSelected(True)
            if self.image_field_combo.count() > 0:
                self.image_field_combo.setCurrentIndex(self.image_field_combo.count() - 1)
            self.placement_combo.setCurrentIndex(1) # Default to 'append'

        # Unblock signals
        self.query_fields_list.blockSignals(False)
        self.image_field_combo.blockSignals(False)
        self.placement_combo.blockSignals(False)

    def save_note_type_config(self, note_type):
        nt_id = str(note_type['id'])
        configs = self.config.setdefault("configs_by_notetype_id", {})
        
        selected_query_items = self.query_fields_list.selectedItems()
        query_fields = [item.text() for item in selected_query_items]
        
        image_field = self.image_field_combo.currentText()
        placement = self.placement_combo.currentData()

        configs[nt_id] = {
            "query_fields": query_fields,
            "image_field": image_field,
            "image_placement": placement
        }
        self.dirty = False

    def mark_dirty(self, *args):
        self.dirty = True

    def reset_to_default(self):
        current_row = self.note_types_list.currentRow()
        if current_row < 0:
            return

        self.query_fields_list.blockSignals(True)
        self.image_field_combo.blockSignals(True)
        self.placement_combo.blockSignals(True)

        self.query_fields_list.clearSelection()

        if self.query_fields_list.count() > 0:
            self.query_fields_list.item(0).setSelected(True)
        if self.image_field_combo.count() > 0:
            self.image_field_combo.setCurrentIndex(self.image_field_combo.count() - 1)
        self.placement_combo.setCurrentIndex(1) # Default to 'append'

        self.query_fields_list.blockSignals(False)
        self.image_field_combo.blockSignals(False)
        self.placement_combo.blockSignals(False)
        self.mark_dirty()

    def save_and_close(self):
        # Save per-note-type settings
        current_row = self.note_types_list.currentRow()
        if current_row >= 0 and self.dirty:
            self.save_note_type_config(self.note_types[current_row])
        
        # Clean up old root-level config keys
        self.config.pop("query_fields", None)
        self.config.pop("query_field", None)
        self.config.pop("image_field", None)
        self.config.pop("search_engine", None)

        mw.addonManager.writeConfig(__name__, self.config)
        self.accept()

def settings_dialog():
    dialog = SettingsDialog(mw)
    dialog.exec()

def init_menu():
    action = QAction("Image Search v3 Settings", mw)
    qconnect(action.triggered, settings_dialog)
    mw.form.menuTools.addAction(action)
