# tabs/support_tab.py

from __future__ import annotations

import os

from aqt.qt import (
    QApplication,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPixmap,
    QPushButton,
    QScrollArea,
    Qt,
    QVBoxLayout,
    QWidget,
)
from aqt.webview import AnkiWebView

from .. import utils
from ._base import TabPage


class SupportTab(TabPage):
    title = "Support"

    def __init__(self, config: dict, on_dirty, parent=None):
        super().__init__(config, on_dirty, parent)

        # Ko-fi floating widget at the top.
        kofi = AnkiWebView(self)
        kofi.setFixedHeight(40)
        kofi_html = """
        <html>
        <head>
        <style>
          body { background-color: transparent; margin: 0; padding: 0; overflow: hidden; }
        </style>
        <script type='text/javascript' src='https://storage.ko-fi.com/cdn/widget/Widget_2.js'></script>
        <script type='text/javascript'>
          kofiwidget2.init('Support me on Ko-fi', '#72a4f2', 'D1D01W6NQT');
          kofiwidget2.draw();
        </script>
        </head>
        <body></body>
        </html>
        """
        kofi.setHtml(kofi_html)
        self.body.addWidget(kofi)

        # Scrollable section with QR codes and copy buttons.
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.body.addWidget(scroll)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll.setWidget(scroll_content)

        intro = QLabel("If you find this addon useful, please consider supporting the developer.")
        intro.setWordWrap(True)
        intro.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        scroll_layout.addWidget(intro)

        self._add_address(
            scroll_layout,
            "UPI (India)",
            "athulkrishnasv2015-2@okhdfcbank",
            "UPI.jpg",
        )
        self._add_address(
            scroll_layout,
            "Bitcoin (BTC)",
            "bc1qrrek3m7sr33qujjrktj949wav6mehdsk057cfx",
            "BTC.jpg",
        )
        self._add_address(
            scroll_layout,
            "Ethereum (ETH)",
            "0xce6899e4903EcB08bE5Be65E44549fadC3F45D27",
            "ETH.jpg",
        )

        scroll_layout.addStretch()

    def _add_address(self, parent_layout, title, address, img_name):
        group = QGroupBox(title)
        layout = QVBoxLayout(group)

        addr_h = QHBoxLayout()
        addr_edit = QLineEdit(address)
        addr_edit.setReadOnly(True)
        addr_h.addWidget(addr_edit)

        copy_btn = QPushButton("Copy")
        copy_btn.setFixedWidth(60)
        copy_btn.clicked.connect(
            lambda: QApplication.clipboard().setText(address)
        )
        addr_h.addWidget(copy_btn)
        layout.addLayout(addr_h)

        img_path = utils.path_to("Support", img_name)
        if os.path.exists(img_path):
            img_label = QLabel()
            pixmap = QPixmap(img_path)
            scaled = pixmap.scaled(
                400, 400,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            img_label.setPixmap(scaled)
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_label.setStyleSheet(
                "margin-top: 5px; border: 1px solid #ccc; padding: 5px; background: white;"
            )
            layout.addWidget(img_label)
        else:
            err = QLabel(f"QR code not found at {img_path}.")
            err.setStyleSheet("color: red;")
            layout.addWidget(err)

        parent_layout.addWidget(group)
