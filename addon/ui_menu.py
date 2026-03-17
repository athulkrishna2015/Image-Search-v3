import os
from aqt import mw
from aqt.utils import qconnect
from aqt.qt import *
from . import utils

_MENU_INSTALLED = False
_MW_MENU_FLAG = "_imgsearchv3_menu_installed"


def _safe_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Image Search v3 Settings")
        self.setMinimumWidth(720)

        self.config = utils.get_config() or {}
        self.note_types = mw.col.models.all() if mw and mw.col else []
        self.nt_dirty = False
        self.net_dirty = False

        # Ensure status_label exists before any signal may trigger dirty handlers.
        self.status_label = QLabel("", self)

        # --- Root layout with tabs ---
        v_layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        v_layout.addWidget(self.tabs)

        # =========================
        # Tab 1: Note Types (per-model)
        # =========================
        self.nt_tab = QWidget(self)
        self.tabs.addTab(self.nt_tab, "Note Types")
        nt_layout = QHBoxLayout(self.nt_tab)

        # Left: note types list
        self.note_types_list = QListWidget(self.nt_tab)
        self.note_types_list.addItems([nt["name"] for nt in self.note_types])
        self.note_types_list.currentItemChanged.connect(self.on_note_type_selected)
        nt_layout.addWidget(self.note_types_list, 1)

        # Right: per-note-type settings
        right_side = QWidget(self.nt_tab)
        self.right_layout = QVBoxLayout(right_side)
        nt_layout.addWidget(right_side, 2)

        self.right_layout.addWidget(QLabel("Settings for selected note type:", right_side))

        # Query Fields
        self.right_layout.addWidget(QLabel("Query Fields (for searching):", right_side))
        self.query_fields_list = QListWidget(right_side)
        self.query_fields_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.query_fields_list.itemSelectionChanged.connect(self.mark_nt_dirty)
        self.right_layout.addWidget(self.query_fields_list)

        # Image Field
        self.right_layout.addWidget(QLabel("Image Field (for placing image):", right_side))
        self.image_field_combo = QComboBox(right_side)
        self.image_field_combo.currentIndexChanged.connect(self.mark_nt_dirty)
        self.right_layout.addWidget(self.image_field_combo)

        # Image Placement
        self.right_layout.addWidget(QLabel("Image Placement:", right_side))
        self.placement_combo = QComboBox(right_side)
        self.placement_combo.addItem("Replace field content", "replace")
        self.placement_combo.addItem("Append to field", "append")
        self.placement_combo.addItem("Prepend to field", "prepend")
        self.placement_combo.currentIndexChanged.connect(self.mark_nt_dirty)
        self.right_layout.addWidget(self.placement_combo)

        # Reset per-note-type defaults button
        nt_buttons_row = QHBoxLayout()
        self.reset_nt_button = QPushButton("Reset Note-Type Defaults", right_side)
        self.reset_nt_button.clicked.connect(self.reset_nt_to_default)
        nt_buttons_row.addWidget(self.reset_nt_button)
        nt_buttons_row.addStretch()
        self.right_layout.addLayout(nt_buttons_row)

        # =========================
        # Tab 2: Provider & Network (global)
        # =========================
        self.net_tab = QWidget(self)
        self.tabs.addTab(self.net_tab, "Network")
        net_v = QVBoxLayout(self.net_tab)

        # Provider group
        prov_group = QGroupBox("Image provider", self.net_tab)
        prov_form = QFormLayout(prov_group)

        self.provider_combo = QComboBox(prov_group)
        self.provider_combo.addItem("Yandex", "yandex")
        self.provider_combo.addItem("DuckDuckGo (hidden API)", "duckduckgo")
        self.provider_combo.addItem("Google (Custom Search)", "google")
        self.provider_combo.currentIndexChanged.connect(self.mark_net_dirty)
        curr_provider = (self.config.get("provider") or "yandex")
        if curr_provider == "ddg":
            curr_provider = "duckduckgo"
        idx = self.provider_combo.findData(curr_provider)
        if idx != -1:
            self.provider_combo.setCurrentIndex(idx)
        prov_form.addRow("Provider:", self.provider_combo)

        self.google_key_edit = QLineEdit(prov_group)
        self.google_key_edit.setPlaceholderText("AIza... (API key)")
        self.google_key_edit.setText(self.config.get("google_api_key", ""))
        self.google_key_edit.textChanged.connect(self.mark_net_dirty)
        prov_form.addRow("Google API key:", self.google_key_edit)

        self.google_cx_edit = QLineEdit(prov_group)
        self.google_cx_edit.setPlaceholderText("cx like: 000000000000000000000:abcdefghi")
        self.google_cx_edit.setText(self.config.get("google_cx", ""))
        self.google_cx_edit.textChanged.connect(self.mark_net_dirty)
        prov_form.addRow("Google CSE ID (cx):", self.google_cx_edit)
        
        # Fallback toggle
        self.google_fallback_chk = QCheckBox(prov_group)
        self.google_fallback_chk.setText("Fallback to Yandex if Google returns no results/errors")
        self.google_fallback_chk.setChecked(bool(self.config.get("google_fallback_to_yandex", True)))
        self.google_fallback_chk.toggled.connect(self.mark_net_dirty)
        prov_form.addRow("Google fallback:", self.google_fallback_chk)

        def _update_google_fields_enabled():
            use_google = self.provider_combo.currentData() == "google"
            self.google_key_edit.setEnabled(use_google)
            self.google_cx_edit.setEnabled(use_google)
            # NEW:
            self.google_fallback_chk.setEnabled(use_google)

        _update_google_fields_enabled()
        self.provider_combo.currentIndexChanged.connect(lambda _=None: _update_google_fields_enabled())

        net_v.addWidget(prov_group)

        # Network group (timeouts/retries/backoff)
        net_group = QGroupBox("Request settings", self.net_tab)
        net_form = QFormLayout(net_group)

        # Request timeout (s)
        self.timeout_spin = QDoubleSpinBox(net_group)
        self.timeout_spin.setRange(1.0, 120.0)
        self.timeout_spin.setSingleStep(0.25)
        self.timeout_spin.setDecimals(2)
        self.timeout_spin.setValue(_safe_float(self.config.get("request_timeout_s", 10.0), 10.0))
        self.timeout_spin.valueChanged.connect(self.mark_net_dirty)
        net_form.addRow("Request timeout (s):", self.timeout_spin)

        # Max retries
        self.retries_spin = QSpinBox(net_group)
        self.retries_spin.setRange(0, 10)
        self.retries_spin.setValue(_safe_int(self.config.get("max_retries", 5), 5))
        self.retries_spin.valueChanged.connect(self.mark_net_dirty)
        net_form.addRow("Max retries:", self.retries_spin)

        # Backoff base (s)
        self.backoff_spin = QDoubleSpinBox(net_group)
        self.backoff_spin.setRange(0.05, 10.0)
        self.backoff_spin.setSingleStep(0.05)
        self.backoff_spin.setDecimals(2)
        self.backoff_spin.setValue(_safe_float(self.config.get("backoff_base_s", 0.75), 0.75))
        self.backoff_spin.valueChanged.connect(self.mark_net_dirty)
        net_form.addRow("Backoff base (s):", self.backoff_spin)

        net_v.addWidget(net_group)

        net_buttons_row = QHBoxLayout()
        self.reset_net_button = QPushButton("Reset Network Defaults", self.net_tab)
        self.reset_net_button.clicked.connect(self.reset_net_to_default)
        net_buttons_row.addWidget(self.reset_net_button)
        net_buttons_row.addStretch()
        net_v.addLayout(net_buttons_row)

        # =========================
        # Tab 3: Support
        # =========================
        self.support_tab = QWidget(self)
        self.tabs.addTab(self.support_tab, "Support")
        sup_v = QVBoxLayout(self.support_tab)

        scroll = QScrollArea(self.support_tab)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        sup_v.addWidget(scroll)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll.setWidget(scroll_content)

        intro_label = QLabel("If you find this addon useful, please consider supporting the developer.")
        intro_label.setWordWrap(True)
        intro_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        scroll_layout.addWidget(intro_label)

        def add_support_section(title, address, img_name):
            group = QGroupBox(title)
            layout = QVBoxLayout(group)

            # Horizontal layout for address and copy button
            addr_h = QHBoxLayout()
            addr_edit = QLineEdit(address)
            addr_edit.setReadOnly(True)
            addr_h.addWidget(addr_edit)

            copy_btn = QPushButton("Copy")
            copy_btn.setFixedWidth(60)
            def copy_text():
                QApplication.clipboard().setText(address)
                self.status_label.setText(f"Copied {title} address to clipboard.")
            copy_btn.clicked.connect(copy_text)
            addr_h.addWidget(copy_btn)
            
            layout.addLayout(addr_h)

            img_path = utils.path_to("Support", img_name)
            if os.path.exists(img_path):
                img_label = QLabel()
                pixmap = QPixmap(img_path)
                # Scale pixmap to fit nicely
                scaled_pixmap = pixmap.scaled(
                    400, 400, 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                img_label.setPixmap(scaled_pixmap)
                img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                img_label.setStyleSheet("margin-top: 5px; border: 1px solid #ccc; padding: 5px; background: white;")
                layout.addWidget(img_label)
            else:
                error_label = QLabel(f"QR code not found at {img_path}.")
                error_label.setStyleSheet("color: red;")
                layout.addWidget(error_label)

            scroll_layout.addWidget(group)

        add_support_section("UPI (India)", "athulkrishnasv2015-2@okhdfcbank", "UPI.jpg")
        add_support_section("Bitcoin (BTC)", "bc1qrrek3m7sr33qujjrktj949wav6mehdsk057cfx", "BTC.jpg")
        add_support_section("Ethereum (ETH)", "0xce6899e4903EcB08bE5Be65E44549fadC3F45D27", "ETH.jpg")

        scroll_layout.addStretch()

        # =========================
        # Bottom status + buttons
        # =========================
        # Add the pre-created label to the layout now
        self.status_label.setStyleSheet("color: #2e7d32;")
        v_layout.addWidget(self.status_label)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        # Save should NOT close the dialog
        save_btn = button_box.button(QDialogButtonBox.StandardButton.Save)
        save_btn.clicked.connect(self.save_only)
        save_close_btn = button_box.addButton("Save and Close", QDialogButtonBox.ButtonRole.AcceptRole)
        save_close_btn.clicked.connect(self.save_and_close)
        button_box.rejected.connect(self.reject)
        v_layout.addWidget(button_box)

        # Initialize first selection (after status_label exists)
        if self.note_types:
            self.note_types_list.setCurrentRow(0)

    # ----- Note-types tab logic -----
    def on_note_type_selected(self, current, previous):
        if self.nt_dirty and previous:
            ret = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"You have unsaved changes for '{previous.text()}'. Save before switching?",
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
        self.nt_dirty = False
        self.clear_status()

    def load_note_type_config(self, note_type):
        # Block signals to avoid spurious dirty
        self.query_fields_list.blockSignals(True)
        self.image_field_combo.blockSignals(True)
        self.placement_combo.blockSignals(True)

        field_names = [f["name"] for f in note_type["flds"]]
        nt_id = str(note_type["id"])

        # Populate fields
        self.query_fields_list.clear()
        self.query_fields_list.addItems(field_names)
        self.image_field_combo.clear()
        self.image_field_combo.addItems(field_names)

        # Load config
        configs = self.config.setdefault("configs_by_notetype_id", {})
        nt_config = configs.get(nt_id)

        if nt_config:
            # Query fields
            selected_query_fields = nt_config.get("query_fields", [])
            for i in range(self.query_fields_list.count()):
                item = self.query_fields_list.item(i)
                item.setSelected(item.text() in selected_query_fields)

            # Image field
            image_field = nt_config.get("image_field")
            if image_field in field_names:
                self.image_field_combo.setCurrentText(image_field)
            else:
                if self.image_field_combo.count() > 0:
                    self.image_field_combo.setCurrentIndex(self.image_field_combo.count() - 1)

            # Placement
            placement = nt_config.get("image_placement", "replace")
            index = self.placement_combo.findData(placement)
            if index != -1:
                self.placement_combo.setCurrentIndex(index)
        else:
            # Defaults
            if self.query_fields_list.count() > 0:
                self.query_fields_list.item(0).setSelected(True)
            if self.image_field_combo.count() > 0:
                self.image_field_combo.setCurrentIndex(self.image_field_combo.count() - 1)
            self.placement_combo.setCurrentIndex(0)  # 'replace'

        # Unblock
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
        self.nt_dirty = False

    def reset_nt_to_default(self):
        # Temporarily block to avoid spurious dirty
        self.query_fields_list.blockSignals(True)
        self.image_field_combo.blockSignals(True)
        self.placement_combo.blockSignals(True)

        self.query_fields_list.clearSelection()
        if self.query_fields_list.count() > 0:
            self.query_fields_list.item(0).setSelected(True)

        if self.image_field_combo.count() > 0:
            self.image_field_combo.setCurrentIndex(self.image_field_combo.count() - 1)

        self.placement_combo.setCurrentIndex(0)

        # Unblock
        self.query_fields_list.blockSignals(False)
        self.image_field_combo.blockSignals(False)
        self.placement_combo.blockSignals(False)

        self.mark_nt_dirty()

    # ----- Network tab helpers -----
    def reset_net_to_default(self):
        self.provider_combo.setCurrentIndex(self.provider_combo.findData("yandex"))
        self.google_key_edit.setText("")
        self.google_cx_edit.setText("")
        self.timeout_spin.setValue(10.0)
        self.retries_spin.setValue(5)
        self.backoff_spin.setValue(0.75)
        self.google_fallback_chk.setChecked(True)
        self.mark_net_dirty()

    # ----- Common -----
    def clear_status(self):
        # Defensive guard in case initialization was interrupted.
        if hasattr(self, "status_label") and self.status_label:
            self.status_label.setText("")

    def mark_nt_dirty(self, *args):
        self.nt_dirty = True
        self.clear_status()

    def mark_net_dirty(self, *args):
        self.net_dirty = True
        self.clear_status()

    def save_only(self):
        # Save per-note-type for the currently selected model
        current_row = self.note_types_list.currentRow()
        if current_row >= 0:
            self.save_note_type_config(self.note_types[current_row])

        # Save global provider + network
        self.config["provider"] = self.provider_combo.currentData()
        self.config["google_api_key"] = self.google_key_edit.text().strip()
        self.config["google_cx"] = self.google_cx_edit.text().strip()
        self.config["request_timeout_s"] = float(self.timeout_spin.value())
        self.config["max_retries"] = int(self.retries_spin.value())
        self.config["backoff_base_s"] = float(self.backoff_spin.value())
        self.config["google_fallback_to_yandex"] = bool(self.google_fallback_chk.isChecked())

        # Clean legacy root-level keys if present
        self.config.pop("query_fields", None)
        self.config.pop("query_field", None)
        self.config.pop("image_field", None)
        self.config.pop("search_engine", None)

        try:
            mw.addonManager.writeConfig(__name__, self.config)
            if hasattr(self, "status_label") and self.status_label:
                self.status_label.setText("Saved.")
            self.nt_dirty = False
            self.net_dirty = False
        except Exception:
            if hasattr(self, "status_label") and self.status_label:
                self.status_label.setText("Could not save settings.")

    def save_and_close(self):
        self.save_only()
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
        if existing.objectName() == "imgsearchv3_settings_action" or existing.text() == "Image Search v3 Settings":
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
