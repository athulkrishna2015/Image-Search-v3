# tabs/_base.py

from __future__ import annotations

from aqt.qt import QWidget, QVBoxLayout


class TabPage(QWidget):
    """
    Convenience base for tabs in the settings dialog.

    Subclasses set `title` and add widgets to `self.body`. The dirty
    callback and shared config dict are provided by the dialog.
    """

    title: str = "Tab"

    def __init__(self, config: dict, on_dirty, parent=None):
        super().__init__(parent)
        self.config = config
        self.on_dirty = on_dirty
        self._layout = QVBoxLayout(self)
        self.setLayout(self._layout)

    @property
    def body(self) -> QVBoxLayout:
        return self._layout

    def mark_dirty(self, *_args):
        if callable(self.on_dirty):
            self.on_dirty()
