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

    # ---- Log health scan used by the "Check log file" button ----
    def check_log_file(self, max_bytes: int = 256 * 1024) -> dict:
        """
        Scan the log file for known error / bug patterns and return a
        structured report. Cheap: reads at most `max_bytes` from the tail
        of the file. Intended to be invoked from the Logs tab's
        "Check log file" button.

        Returns:
            {
                "exists": bool,
                "size_bytes": int,
                "checked_bytes": int,
                "line_count": int,
                "findings": [
                    {"pattern": str, "category": str, "count": int,
                     "first_line_no": int, "last_line_no": int,
                     "sample": str},
                    ...
                ],
            }
        """
        report_obj = {
            "exists": os.path.exists(LOG_FILE),
            "size_bytes": 0,
            "checked_bytes": 0,
            "line_count": 0,
            "findings": [],
        }
        if not report_obj["exists"]:
            return report_obj

        try:
            report_obj["size_bytes"] = os.path.getsize(LOG_FILE)
            with open(LOG_FILE, "rb") as fh:
                if report_obj["size_bytes"] > max_bytes:
                    fh.seek(report_obj["size_bytes"] - max_bytes)
                    data = fh.read()
                    truncated = True
                else:
                    data = fh.read()
                    truncated = False
            text = data.decode("utf-8", errors="replace")
        except Exception as exc:
            report_obj["error"] = repr(exc)
            return report_obj

        report_obj["checked_bytes"] = len(data)
        if truncated:
            report_obj["checked_bytes_note"] = (
                f"Only the last {max_bytes} bytes were checked; the file "
                f"is {report_obj['size_bytes']} bytes total."
            )

        lines = text.splitlines()
        report_obj["line_count"] = len(lines)

        # Patterns: (category, regex). The "category" is the user-facing
        # group; the regex is matched against each line.
        for category, regex in _LOG_PATTERNS:
            compiled = re.compile(regex, re.IGNORECASE)
            count = 0
            first_line = None
            last_line = None
            sample = None
            for i, line in enumerate(lines, start=1):
                if compiled.search(line):
                    if first_line is None:
                        first_line = i
                    last_line = i
                    sample = line[:240]
                    count += 1
            if count:
                report_obj["findings"].append({
                    "category": category,
                    "pattern": regex,
                    "count": count,
                    "first_line_no": first_line,
                    "last_line_no": last_line,
                    "sample": sample,
                })
        return report_obj

    def maybe_clear_on_startup(self, config: dict | None) -> bool:
        """
        Clear the log if `config['clear_logs_on_startup']` is truthy.
        Returns True if the log file existed and was truncated, False
        otherwise (including when the user has disabled the option, or
        when the log file does not exist yet). Safe to call from
        add-on import.
        """
        cfg = config or {}
        if not cfg.get("clear_logs_on_startup", True):
            return False
        if not os.path.exists(LOG_FILE):
            return False
        return self.clear()


# Patterns the "Check log file" scanner looks for. Order matters only
# for tie-breaking in the report UI; each pattern is evaluated
# independently.
_LOG_PATTERNS = (
    ("Traceback", r"Traceback \(most recent call last\)"),
    ("UnboundLocalError", r"UnboundLocalError"),
    ("FileNotFoundError", r"FileNotFoundError"),
    ("PermissionError", r"PermissionError|denied"),
    ("JSON decode error", r"JSONDecodeError|Expecting value|invalid json"),
    ("HTTP 4xx/5xx", r"\b(4\d\d|5\d\d)\b.*(?:status|http)"),
    ("SSL / certificate", r"SSLError|certificate verify|ssl\.c"),
    ("ConnectionError", r"ConnectionError|Connection refused|Connection reset"),
    ("Timeout", r"Timeout|timed out|read timeout"),
    ("yimages giving up", r"yimages: giving up"),
    ("gimages giving up", r"gimages: giving up"),
    ("ddg giving up", r"ddg: (giving up|no vqd)"),
    ("Disk full", r"No space left on device"),
    ("Settings save failed", r"Settings save failed"),
    ("addonMeta write failed", r"writeAddonMeta failed"),
)


log = _AddonLogger()
