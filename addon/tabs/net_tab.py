# tabs/net_tab.py

from __future__ import annotations

from aqt.qt import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..utils import safe_float, safe_int
from ._base import TabPage


class NetworkTab(TabPage):
    title = "Network"

    def __init__(self, config: dict, on_dirty, parent=None):
        super().__init__(config, on_dirty, parent)

        outer = QVBoxLayout()
        # We don't use self.body directly so the spinboxes/forms can keep
        # their own layout. Re-attach outer to body via a wrapper widget.
        wrapper = QWidget(self)
        wrapper.setLayout(outer)
        self.body.addWidget(wrapper)

        # --- Provider group ---
        prov_group = QGroupBox("Image provider", wrapper)
        prov_form = QFormLayout(prov_group)

        self.provider_combo = QComboBox(prov_group)
        self.provider_combo.addItem("Yandex", "yandex")
        self.provider_combo.addItem("DuckDuckGo (hidden API)", "duckduckgo")
        self.provider_combo.addItem("Google (Custom Search)", "google")
        self.provider_combo.currentIndexChanged.connect(self._on_dirty)
        cur_provider = (self.config.get("provider") or "yandex")
        if cur_provider == "ddg":
            cur_provider = "duckduckgo"
        idx = self.provider_combo.findData(cur_provider)
        if idx != -1:
            self.provider_combo.setCurrentIndex(idx)
        prov_form.addRow("Provider:", self.provider_combo)

        self.google_key_edit = QLineEdit(prov_group)
        self.google_key_edit.setPlaceholderText("AIza... (API key)")
        self.google_key_edit.setText(self.config.get("google_api_key", ""))
        self.google_key_edit.textChanged.connect(self._on_dirty)
        prov_form.addRow("Google API key:", self.google_key_edit)

        self.google_cx_edit = QLineEdit(prov_group)
        self.google_cx_edit.setPlaceholderText("cx like: 000000000000000000000:abcdefghi")
        self.google_cx_edit.setText(self.config.get("google_cx", ""))
        self.google_cx_edit.textChanged.connect(self._on_dirty)
        prov_form.addRow("Google CSE ID (cx):", self.google_cx_edit)

        self.google_fallback_chk = QCheckBox(prov_group)
        self.google_fallback_chk.setText(
            "Fallback to Yandex if Google returns no results/errors"
        )
        self.google_fallback_chk.setChecked(
            bool(self.config.get("google_fallback_to_yandex", True))
        )
        self.google_fallback_chk.toggled.connect(self._on_dirty)
        prov_form.addRow("Google fallback:", self.google_fallback_chk)

        outer.addWidget(prov_group)

        # --- Network group ---
        net_group = QGroupBox("Request settings", wrapper)
        net_form = QFormLayout(net_group)

        self.timeout_spin = QDoubleSpinBox(net_group)
        self.timeout_spin.setRange(1.0, 120.0)
        self.timeout_spin.setSingleStep(0.25)
        self.timeout_spin.setDecimals(2)
        self.timeout_spin.setValue(
            safe_float(self.config.get("request_timeout_s", 10.0), 10.0)
        )
        self.timeout_spin.valueChanged.connect(self._on_dirty)
        net_form.addRow("Request timeout (s):", self.timeout_spin)

        self.retries_spin = QSpinBox(net_group)
        self.retries_spin.setRange(0, 10)
        self.retries_spin.setValue(safe_int(self.config.get("max_retries", 5), 5))
        self.retries_spin.valueChanged.connect(self._on_dirty)
        net_form.addRow("Max retries:", self.retries_spin)

        self.backoff_spin = QDoubleSpinBox(net_group)
        self.backoff_spin.setRange(0.05, 10.0)
        self.backoff_spin.setSingleStep(0.05)
        self.backoff_spin.setDecimals(2)
        self.backoff_spin.setValue(
            safe_float(self.config.get("backoff_base_s", 0.75), 0.75)
        )
        self.backoff_spin.valueChanged.connect(self._on_dirty)
        net_form.addRow("Backoff base (s):", self.backoff_spin)

        outer.addWidget(net_group)

        # Reset button
        buttons_row = QHBoxLayout()
        reset_btn = QPushButton("Reset Network Defaults", wrapper)
        reset_btn.clicked.connect(self.reset_to_default)
        buttons_row.addWidget(reset_btn)
        buttons_row.addStretch()
        outer.addLayout(buttons_row)

        outer.addStretch()

        # Enable/disable Google fields based on selected provider.
        self.provider_combo.currentIndexChanged.connect(self._refresh_google_enabled)
        self._refresh_google_enabled()

    def _refresh_google_enabled(self, *_):
        use_google = self.provider_combo.currentData() == "google"
        self.google_key_edit.setEnabled(use_google)
        self.google_cx_edit.setEnabled(use_google)
        self.google_fallback_chk.setEnabled(use_google)

    def _on_dirty(self, *_):
        self.mark_dirty()

    def collect(self) -> dict:
        return {
            "provider": self.provider_combo.currentData(),
            "google_api_key": self.google_key_edit.text().strip(),
            "google_cx": self.google_cx_edit.text().strip(),
            "request_timeout_s": float(self.timeout_spin.value()),
            "max_retries": int(self.retries_spin.value()),
            "backoff_base_s": float(self.backoff_spin.value()),
            "google_fallback_to_yandex": bool(self.google_fallback_chk.isChecked()),
        }

    def reset_to_default(self):
        self.provider_combo.setCurrentIndex(self.provider_combo.findData("yandex"))
        self.google_key_edit.setText("")
        self.google_cx_edit.setText("")
        self.timeout_spin.setValue(10.0)
        self.retries_spin.setValue(5)
        self.backoff_spin.setValue(0.75)
        self.google_fallback_chk.setChecked(True)
        self._on_dirty()
