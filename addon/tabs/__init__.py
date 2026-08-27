# tabs/__init__.py

from __future__ import annotations

from .nt_tab import NoteTypesTab
from .net_tab import NetworkTab
from .log_tab import LogsTab
from .tab_support import SupportTabMixin
from .widgets import ADDON_PACKAGE

__all__ = [
    "NoteTypesTab",
    "NetworkTab",
    "LogsTab",
    "SupportTabMixin",
    "ADDON_PACKAGE",
]
