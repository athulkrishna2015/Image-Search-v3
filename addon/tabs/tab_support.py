# -*- coding: utf-8 -*-

import os
from aqt import mw
from aqt.utils import openLink
from aqt.qt import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QPixmap,
    Qt,
)
from aqt.webview import AnkiWebView
from .widgets import ADDON_PACKAGE

class SupportTabMixin:
    def _create_support_tab(self):
        self.support_tab = QWidget()
        layout = QVBoxLayout(self.support_tab)
        layout.setContentsMargins(10, 10, 10, 10)

        instr = QLabel(
            "If you find this addon useful, consider supporting the development through the following methods:"
        )
        instr.setWordWrap(True)
        instr.setOpenExternalLinks(True)
        instr.setTextFormat(Qt.TextFormat.RichText)
        instr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(instr)

        
        # Supporter Opt-out (Moved to top near message)
        self.supporter_check = QCheckBox("I have supported this addon (Hide automatic update welcome)")
        self.supporter_check.setToolTip("Checking this will prevent the Support tab from opening automatically after future updates.")
        self.supporter_check.toggled.connect(self.on_supporter_check_toggled)
        layout.addWidget(self.supporter_check, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(10)

        # Scroll area for QR codes
        scroll = QScrollArea(self.support_tab)
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.qr_list = QVBoxLayout(scroll_content)
        self.qr_list.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.qr_list.setSpacing(30)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Ko-fi Widget (Embedded Script via AnkiWebView)
        self.support_webview = AnkiWebView(self.support_tab)
        self.support_webview.setFixedHeight(42)
        kofi_html = """
        <html>
        <head>
        <style>
          body { background-color: transparent; margin: 0; padding: 0; overflow: hidden; text-align: center; line-height: 42px; }
          .kofi-button-col { display: inline-block; vertical-align: middle; }
        </style>
        </head>
        <body>
        <script type='text/javascript' src='https://storage.ko-fi.com/cdn/widget/Widget_2.js'></script>
        <script type='text/javascript'>
          kofiwidget2.init('Support me on Ko-fi', '#72a4f2', 'D1D01W6NQT');
          kofiwidget2.draw();
        </script>
        </body>
        </html>
        """
        self.support_webview.setHtml(kofi_html)
        layout.addWidget(self.support_webview)

        base_path = os.path.dirname(os.path.dirname(__file__))

        def add_qr(name, address, filename):
            container = QWidget()
            vbox = QVBoxLayout(container)
            vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)

            title = QLabel(f"<b>{name}</b>")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(title)

            qr_label = QLabel()
            qr_path = os.path.join(base_path, "Support", filename)
            pixmap = QPixmap(qr_path)
            if not pixmap.isNull():
                qr_label.setPixmap(pixmap.scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                qr_label.setText("Image not found")
            qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(qr_label)

            addr_row_container = QWidget()
            addr_row_container.setFixedWidth(420) # Slightly wider
            addr_row = QHBoxLayout(addr_row_container)
            addr_row.setContentsMargins(10, 0, 10, 0)
            addr_row.setSpacing(10)

            addr_label = QLineEdit(address)
            addr_label.setReadOnly(True)
            addr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            addr_label.setStyleSheet("background: rgba(0,0,0,5%); border: 1px solid rgba(0,0,0,10%); border-radius: 3px; padding: 2px;")
            addr_label.setMinimumWidth(0)
            
            copy_btn = QPushButton("Copy")
            copy_btn.setFixedWidth(80) # Increased from 60
            copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            
            def on_copy(_=None, addr=address, btn=copy_btn):
                clipboard = QApplication.clipboard()
                if clipboard:
                    clipboard.setText(addr)
                    btn.setText("Copied!")
                    from aqt.qt import QTimer
                    QTimer.singleShot(2000, lambda: btn.setText("Copy"))
            
            copy_btn.clicked.connect(on_copy)
            
            addr_row.addWidget(addr_label, 1)
            addr_row.addWidget(copy_btn)
            vbox.addWidget(addr_row_container, 0, Qt.AlignmentFlag.AlignCenter)

            self.qr_list.addWidget(container)

        add_qr("UPI", "athulkrishnasv2015-2@okhdfcbank", "UPI.jpg")
        add_qr("BTC", "bc1qrrek3m7sr33qujjrktj949wav6mehdsk057cfx", "BTC.jpg")
        add_qr("ETH", "0xce6899e4903EcB08bE5Be65E44549fadC3F45D27", "ETH.jpg")

        self.load_supporter_state()
        return self.support_tab

    def load_supporter_state(self):
        meta = mw.addonManager.addonMeta(ADDON_PACKAGE)
        self.supporter_check.blockSignals(True)
        self.supporter_check.setChecked(meta.get("supporter_opt_out", False))
        self.supporter_check.blockSignals(False)

    def on_supporter_check_toggled(self, checked):
        meta = mw.addonManager.addonMeta(ADDON_PACKAGE)
        meta["supporter_opt_out"] = checked
        mw.addonManager.writeAddonMeta(ADDON_PACKAGE, meta)
