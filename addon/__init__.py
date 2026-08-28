# init.py
from __future__ import annotations


def setup() -> None:
    """Register editor UI and settings menu."""
    # Import inside the function to avoid circular imports / reload loops
    from .ui_editor import init_editor
    from .ui_menu import init_menu
    from . import utils
    from .logger import log

    # Apply the user's log level as early as possible so subsequent
    # log.info(...) calls in this Anki session respect it.
    try:
        cfg = utils.get_config() or {}
        if cfg.get("log_level"):
            log.set_level(cfg["log_level"])
    except Exception:
        pass

    # Auto-clear the log on addon import if the user has the option
    # enabled (default: enabled). This is a single small file write at
    # most and only when the file already exists, so the cost is bounded.
    try:
        cfg = utils.get_config() or {}
        log.maybe_clear_on_startup(cfg)
    except Exception:
        pass

    init_editor()
    init_menu()


# Anki loads an add-on by importing this package. Register its UI at import
# time so the Tools menu and editor toolbar are available in every session.
setup()
