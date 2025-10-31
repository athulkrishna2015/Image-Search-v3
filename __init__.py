from .ui_editor import init_editor
from .ui_menu import init_menu

def _init():
    # Register editor buttons, context menu, and settings menu
    init_editor()
    init_menu()

_init()
