# logger.py

from __future__ import annotations

import logging
import logging.handlers
import os
import re
from os.path import dirname, abspath, realpath
from typing import Optional

CURRENT_DIR = dirname(abspath(realpath(__file__)))

LOG_DIR = os.path.join(CURRENT_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "image_search_v3.log")
LOGGER_NAME = "image_search_v3"

_ALL_LEVEL = -10  # lower than any stdlib level so 3rd-party noise is captured
_LEVELS = {
    "all": _ALL_LEVEL,
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

logging.addLevelName(_ALL_LEVEL, "ALL")

_DEFAULT_LEVEL = "info"
_DEFAULT_MAX_BYTES = 512 * 1024
_DEFAULT_BACKUP_COUNT = 3
_MAX_PREVIEW_BYTES = 64 * 1024

_SAFE_LEVEL_RE = re.compile(r"^[A-Za-z]+$")


class _AddonLogger:
    """
    Lightweight wrapper around stdlib logging so the rest of the add-on
    can call `log.info(...)` / `log.error(...)` without worrying about
    the underlying handler, level, or file location.

    The handler is attached lazily on first use so that importing the
    add-on outside Anki (e.g. from the test suite or the build script)
    never touches the filesystem.
    """

    def __init__(self):
        self._logger = logging.getLogger(LOGGER_NAME)
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        self._handler: Optional[logging.handlers.RotatingFileHandler] = None
        self._current_level_name: str = _DEFAULT_LEVEL

    def _ensure_handler(self) -> None:
        if self._handler is not None:
            return
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
        except Exception:
            return
        try:
            handler = logging.handlers.RotatingFileHandler(
                LOG_FILE,
                maxBytes=_DEFAULT_MAX_BYTES,
                backupCount=_DEFAULT_BACKUP_COUNT,
                encoding="utf-8",
            )
        except Exception:
            return
        fmt = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        handler.setFormatter(fmt)
        self._logger.addHandler(handler)
        self._handler = handler

    def set_level(self, level_name: str) -> None:
        if not _SAFE_LEVEL_RE.match(level_name or ""):
            return
        level = _LEVELS.get(level_name.lower())
        if level is None:
            return
        self._current_level_name = level_name.lower()
        self._logger.setLevel(level)

    def get_level(self) -> str:
        return self._current_level_name

    def log_path(self) -> str:
        return LOG_FILE

    def log_dir(self) -> str:
        return LOG_DIR

    # ---- stdlib-style API ----
    def debug(self, msg, *args, **kwargs):
        self._ensure_handler()
        self._logger.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self._ensure_handler()
        self._logger.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self._ensure_handler()
        self._logger.warning(msg, *args, **kwargs)

    def error(self, msg, *args, exc_info: bool = False, **kwargs):
        self._ensure_handler()
        self._logger.error(msg, *args, exc_info=exc_info, **kwargs)

    def exception(self, msg, *args, **kwargs):
        self._ensure_handler()
        self._logger.exception(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self._ensure_handler()
        self._logger.critical(msg, *args, **kwargs)

    # ---- Maintenance helpers used by the Logs tab ----
    def tail_text(self, max_bytes: int = _MAX_PREVIEW_BYTES) -> str:
        """Return the last `max_bytes` of the current log file as text."""
        if not os.path.exists(LOG_FILE):
            return ""
        try:
            size = os.path.getsize(LOG_FILE)
            with open(LOG_FILE, "rb") as fh:
                if size > max_bytes:
                    fh.seek(size - max_bytes)
                data = fh.read()
            if size > max_bytes:
                return "\n...[truncated]...\n" + data.decode("utf-8", errors="replace")
            return data.decode("utf-8", errors="replace")
        except Exception as exc:
            return f"<could not read log: {exc!r}>"

    def clear(self) -> bool:
        if not os.path.exists(LOG_FILE):
            return True
        try:
            with open(LOG_FILE, "w", encoding="utf-8"):
                pass
            for i in range(_DEFAULT_BACKUP_COUNT):
                bak = f"{LOG_FILE}.{i + 1}"
                if os.path.exists(bak):
                    try:
                        os.remove(bak)
                    except Exception:
                        pass
            return True
        except Exception as exc:
            self.error("Failed to clear log file: %r", exc)
            return False


log = _AddonLogger()
