# tabs/_base.py

from __future__ import annotations

from aqt.qt import QVBoxLayout, QWidget, QScrollArea


class TabPage(QWidget):
    """
    Convenience base for tabs in the settings dialog.

    Subclasses set `title` and add widgets to `self.body`. The dirty
    callback and shared config dict are provided by the dialog.

    The tab's body is wrapped in a QScrollArea so tabs with many
    fields (Network, Note Types with many note types) do not get
    clipped when the dialog is resized small. Subclasses that need
    special internal scroll behaviour (Logs uses a QPlainTextEdit
    which scrolls itself) can set `_scroll_body = False` before
    calling `__init__` to opt out, or they can add widgets directly
    to the inner body widget via `self.body_widget`.
    """

    title: str = "Tab"
    _scroll_body: bool = True

    def __init__(self, config: dict, on_dirty, parent=None):
        super().__init__(parent)
        self.config = config
        self.on_dirty = on_dirty
        self._layout = QVBoxLayout(self)
        self.setLayout(self._layout)

        # Inner body widget that holds the actual tab content. Subclasses
        # add widgets to it via `self.body` (which returns its layout).
        self.body_widget = QWidget(self)

        if self._scroll_body:
            self._scroll = QScrollArea(self)
            self._scroll.setWidgetResizable(True)
            # Keep frame clean (tabs look like dialog sections, not
            # nested dialogs).
            self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            self._layout.addWidget(self._scroll)
            self._scroll.setWidget(self.body_widget)
            # body returns the body widget's layout so subclasses can
            # keep using `self.body.addWidget(...)`.
            self._body_layout = QVBoxLayout(self.body_widget)
            self._body_layout.setContentsMargins(0, 0, 0, 0)
        else:
            # No scroll wrapper; the tab is its own scrollable widget
            # (e.g. Logs uses a QPlainTextEdit which scrolls internally).
            self._layout.addWidget(self.body_widget)
            self._body_layout = QVBoxLayout(self.body_widget)
            self._body_layout.setContentsMargins(0, 0, 0, 0)

    @property
    def body(self) -> QVBoxLayout:
        return self._body_layout

    def mark_dirty(self, *_args):
        if callable(self.on_dirty):
            self.on_dirty()
