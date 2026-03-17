# init.py
from __future__ import annotations

def setup() -> None:
    """Register editor UI and settings menu."""
    # Import inside the function to avoid circular imports / reload loops
    from .ui_editor import init_editor
    from .ui_menu import init_menu
    init_editor()
    init_menu()

# Run on module import (keeps behavior identical to your current file)
setup()
