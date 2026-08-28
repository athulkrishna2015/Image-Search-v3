# tabs/nt_tab.py

from __future__ import annotations

from aqt import mw
from aqt.qt import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ._base import TabPage


class NoteTypesTab(TabPage):
    title = "Note Types"

    def __init__(self, config: dict, on_dirty, parent=None):
        super().__init__(config, on_dirty, parent)
        self.note_types = mw.col.models.all() if mw and mw.col else []
        self.nt_dirty = False

        # Two-column layout: list on the left, settings on the right.
        root = QHBoxLayout()
        self.body.addLayout(root)

        # Left: list of note types
        self.note_types_list = QListWidget(self)
        self.note_types_list.setToolTip("Note type whose image settings are being edited.")
        self.note_types_list.addItems([nt["name"] for nt in self.note_types])
        self.note_types_list.currentItemChanged.connect(self._on_selected)
        root.addWidget(self.note_types_list, 1)

        # Right: settings for the selected note type
        right = QWidget(self)
        right_layout = QVBoxLayout(right)
        root.addWidget(right, 2)

        right_layout.addWidget(QLabel("Settings for selected note type:", right))

        right_layout.addWidget(QLabel("Query Fields (for searching):", right))
        self.query_fields_list = QListWidget(right)
        self.query_fields_list.setToolTip(
            "Select one or more fields whose text is used as the search query."
        )
        self.query_fields_list.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection
        )
        self.query_fields_list.itemSelectionChanged.connect(self._mark_dirty)
        right_layout.addWidget(self.query_fields_list)

        right_layout.addWidget(QLabel("Image Field (for placing image):", right))
        self.image_field_combo = QComboBox(right)
        self.image_field_combo.setToolTip(
            "Field where the downloaded image will be inserted."
        )
        self.image_field_combo.currentIndexChanged.connect(self._mark_dirty)
        right_layout.addWidget(self.image_field_combo)

        right_layout.addWidget(QLabel("Image Placement:", right))
        self.placement_combo = QComboBox(right)
        self.placement_combo.setToolTip(
            "Replace the latest add-on image, append, or prepend the new image."
        )
        self.placement_combo.addItem("Replace field content", "replace")
        self.placement_combo.addItem("Append to field", "append")
        self.placement_combo.addItem("Prepend to field", "prepend")
        self.placement_combo.currentIndexChanged.connect(self._mark_dirty)
        right_layout.addWidget(self.placement_combo)

        buttons_row = QHBoxLayout()
        reset_btn = QPushButton("Reset Note-Type Defaults", right)
        reset_btn.setToolTip(
            "Reset this note type to the first query field, last image field, and replace mode."
        )
        reset_btn.clicked.connect(self.reset_to_default)
        buttons_row.addWidget(reset_btn)
        buttons_row.addStretch()
        right_layout.addLayout(buttons_row)

        # Select the first note type by default.
        if self.note_types:
            self.note_types_list.setCurrentRow(0)

    # ----- public API used by the dialog -----
    def current_note_type(self):
        row = self.note_types_list.currentRow()
        if row < 0 or row >= len(self.note_types):
            return None
        return self.note_types[row]

    def save_current(self):
        nt = self.current_note_type()
        if nt is None:
            return
        nt_id = str(nt["id"])
        configs = self.config.setdefault("configs_by_notetype_id", {})
        configs[nt_id] = {
            "query_fields": [i.text() for i in self.query_fields_list.selectedItems()],
            "image_field": self.image_field_combo.currentText(),
            "image_placement": self.placement_combo.currentData(),
        }
        self.nt_dirty = False

    def clear_dirty(self):
        self.nt_dirty = False

    def is_dirty(self) -> bool:
        return self.nt_dirty

    # ----- internals -----
    def _mark_dirty(self, *_):
        self.nt_dirty = True
        self.mark_dirty()

    def _on_selected(self, current, previous):
        # Warn on unsaved changes.
        if self.nt_dirty and previous is not None:
            ret = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"You have unsaved changes for '{previous.text()}'. Save before switching?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if ret == QMessageBox.StandardButton.Save:
                prev_row = self.note_types_list.row(previous)
                if 0 <= prev_row < len(self.note_types):
                    self._write_nt(self.note_types[prev_row])
            elif ret == QMessageBox.StandardButton.Cancel:
                self.note_types_list.blockSignals(True)
                self.note_types_list.setCurrentItem(previous)
                self.note_types_list.blockSignals(False)
                return

        if current is None:
            return
        row = self.note_types_list.row(current)
        if 0 <= row < len(self.note_types):
            self._load_nt(self.note_types[row])
        self.nt_dirty = False

    def _load_nt(self, note_type):
        self.query_fields_list.blockSignals(True)
        self.image_field_combo.blockSignals(True)
        self.placement_combo.blockSignals(True)

        field_names = [f["name"] for f in note_type["flds"]]
        nt_id = str(note_type["id"])

        self.query_fields_list.clear()
        self.query_fields_list.addItems(field_names)
        self.image_field_combo.clear()
        self.image_field_combo.addItems(field_names)

        configs = self.config.setdefault("configs_by_notetype_id", {})
        nt_config = configs.get(nt_id)
        if nt_config:
            selected = set(nt_config.get("query_fields") or [])
            for i in range(self.query_fields_list.count()):
                item = self.query_fields_list.item(i)
                item.setSelected(item.text() in selected)

            image_field = nt_config.get("image_field")
            if image_field in field_names:
                self.image_field_combo.setCurrentText(image_field)
            elif self.image_field_combo.count() > 0:
                self.image_field_combo.setCurrentIndex(self.image_field_combo.count() - 1)

            idx = self.placement_combo.findData(nt_config.get("image_placement", "replace"))
            if idx != -1:
                self.placement_combo.setCurrentIndex(idx)
        else:
            if self.query_fields_list.count() > 0:
                self.query_fields_list.item(0).setSelected(True)
            if self.image_field_combo.count() > 0:
                self.image_field_combo.setCurrentIndex(self.image_field_combo.count() - 1)
            self.placement_combo.setCurrentIndex(0)

        self.query_fields_list.blockSignals(False)
        self.image_field_combo.blockSignals(False)
        self.placement_combo.blockSignals(False)

    def _write_nt(self, note_type):
        nt_id = str(note_type["id"])
        configs = self.config.setdefault("configs_by_notetype_id", {})
        configs[nt_id] = {
            "query_fields": [i.text() for i in self.query_fields_list.selectedItems()],
            "image_field": self.image_field_combo.currentText(),
            "image_placement": self.placement_combo.currentData(),
        }
        self.nt_dirty = False

    def reset_to_default(self):
        self.query_fields_list.blockSignals(True)
        self.image_field_combo.blockSignals(True)
        self.placement_combo.blockSignals(True)

        self.query_fields_list.clearSelection()
        if self.query_fields_list.count() > 0:
            self.query_fields_list.item(0).setSelected(True)
        if self.image_field_combo.count() > 0:
            self.image_field_combo.setCurrentIndex(self.image_field_combo.count() - 1)
        self.placement_combo.setCurrentIndex(0)

        self.query_fields_list.blockSignals(False)
        self.image_field_combo.blockSignals(False)
        self.placement_combo.blockSignals(False)

        self._mark_dirty()
