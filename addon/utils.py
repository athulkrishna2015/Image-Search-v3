# utils.py

from __future__ import annotations

import html
import os
import re
import socket
import time
import urllib.request
import urllib.error
from os.path import dirname, abspath, realpath
from tempfile import mkstemp

from aqt import mw

CURRENT_DIR = dirname(abspath(realpath(__file__)))

_NET_CHECK_HOSTS = ("yandex.ru", "google.com", "1.1.1.1")
_NET_CHECK_TIMEOUT_S = 1.0

# Default HTTP headers for image downloads to avoid 403/blocks from many hosts
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
_DEFAULT_REFERER = "https://www.google.com"
_ACCEPT_IMG = "image/avif,image/webp,image/*,*/*;q=0.8"

# Throttle for one-shot warning dialogs so we don't spam the user.
_WARNED_KEYS: set[tuple[str, str]] = set()

# Default network settings shared across providers and the download path.
_NET_DEFAULTS = {
    "request_timeout_s": 10.0,
    "max_retries": 5,
    "backoff_base_s": 0.75,
}


def safe_float(value, default, minimum=None, maximum=None):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        try:
            parsed = float(default)
        except (TypeError, ValueError):
            parsed = 0.0
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def safe_int(value, default, minimum=None, maximum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        try:
            parsed = int(default)
        except (TypeError, ValueError):
            parsed = 0
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def get_net_settings():
    """
    Read network settings from the add-on config with safe fallbacks.
    Returns (timeout_s, max_retries, backoff_base_s).
    """
    try:
        cfg = mw.addonManager.getConfig(__name__) or {}
    except Exception:
        cfg = {}
    timeout_s = safe_float(
        cfg.get("request_timeout_s", _NET_DEFAULTS["request_timeout_s"]),
        _NET_DEFAULTS["request_timeout_s"],
        minimum=1.0,
        maximum=120.0,
    )
    max_retries = safe_int(
        cfg.get("max_retries", _NET_DEFAULTS["max_retries"]),
        _NET_DEFAULTS["max_retries"],
        minimum=0,
        maximum=10,
    )
    backoff_base_s = safe_float(
        cfg.get("backoff_base_s", _NET_DEFAULTS["backoff_base_s"]),
        _NET_DEFAULTS["backoff_base_s"],
        minimum=0.05,
        maximum=10.0,
    )
    return timeout_s, max_retries, backoff_base_s


def path_to(*args):
    return os.path.join(CURRENT_DIR, *args)


def get_config():
    return mw.addonManager.getConfig(__name__)


def report(text: str, *, key: tuple | None = None, title: str = "Image Search v3"):
    """
    Show a modal warning. Pass `key` to throttle duplicate warnings (e.g.
    once per note-type id per session).
    """
    if key is not None:
        if key in _WARNED_KEYS:
            return
        _WARNED_KEYS.add(key)
    try:
        from aqt.utils import showWarning

        showWarning(text, title=title)
    except Exception:
        print(text)


def notify(text: str, period_ms: int = 2500):
    """
    Show a lightweight, non-blocking notification inside Anki.
    Falls back to showInfo/print if tooltip is unavailable.
    """
    try:
        from aqt.utils import tooltip

        tooltip(text, period_ms)
        return
    except Exception:
        pass

    try:
        from aqt.utils import showInfo

        showInfo(text, title="Image Search v3")
    except Exception:
        print(text)


def get_note_query(note):
    """
    Return the text to search for this note, using per‑notetype config first,
    then global config, with Cloze‑aware and case‑insensitive matching.
    """
    field_names = mw.col.models.fieldNames(note.model())
    config = get_config()
    nt_id = str(note.model()["id"])

    # 1) Collect preferred query fields (per-notetype, then global)
    query_fields = []
    nt_configs = config.get("configs_by_notetype_id", {})
    if nt_id in nt_configs and nt_configs[nt_id].get("query_fields"):
        query_fields = nt_configs[nt_id]["query_fields"]
    elif "query_fields" in config and config["query_fields"]:
        query_fields = config["query_fields"]
    elif "query_field" in config:
        query_fields = [config["query_field"]]

    # Build a case-insensitive lookup of actual field names
    field_lookup = {fn.strip().lower(): fn for fn in field_names}

    def resolve_candidate(name: str) -> str | None:
        """Return the actual field name to use, or None if not resolvable."""
        key = (name or "").strip().lower()
        # Exact (case-insensitive) match
        if key in field_lookup:
            return field_lookup[key]
        # Cloze-friendly remaps:
        # - 'Front' preference → 'Text' field on Cloze note types
        if key == "front" and "text" in field_lookup:
            return field_lookup["text"]
        # (Optional) map generic 'Back' → 'Back Extra' if it exists on the model
        if key == "back" and "back extra" in field_lookup:
            return field_lookup["back extra"]
        return None

    # 2) Try configured fields in order
    tried = []
    for cand in (query_fields or []):
        tried.append(cand)
        actual = resolve_candidate(cand)
        if actual is not None:
            return note.fields[field_names.index(actual)]

    # 3) Heuristic defaults before warning:
    # Prefer "Text" automatically if available (common on Cloze)
    if "text" in field_lookup:
        return note.fields[field_names.index(field_lookup["text"])]

    # 4) If config specified fields but none matched, warn once, then fall back
    if query_fields:
        report(
            "Could not find any of the configured query fields in the current note type.\n"
            f"Note Type: {note.model()['name']}\n"
            f"Fields available: {', '.join(field_names)}\n"
            f"Fields tried: {', '.join(query_fields)}\n"
            "Falling back to the first field.",
            key=("query_fields_missing", str(note.model()["id"])),
        )

    # 5) Final fallback: first field or empty string
    if field_names:
        return note.fields[0]
    return ""


def get_note_image_field_index(note):
    field_names = mw.col.models.fieldNames(note.model())
    config = get_config()
    nt_id = str(note.model()["id"])

    image_field = None
    nt_configs = config.get("configs_by_notetype_id", {})
    if nt_id in nt_configs and nt_configs[nt_id].get("image_field"):
        image_field = nt_configs[nt_id]["image_field"]
    elif config.get("image_field"):
        image_field = config.get("image_field")

    if image_field:
        try:
            return field_names.index(image_field)
        except ValueError:
            nt_id = str(note.model()["id"])
            if field_names:
                report(
                    f"Could not find the configured image field ('{image_field}') in "
                    f"the current note type ('{note.model()['name']}').\n"
                    f"Available fields: {', '.join(field_names)}\n"
                    f"Falling back to the last field: '{field_names[-1]}'.",
                    key=("image_field_missing", nt_id, image_field),
                )
                return len(field_names) - 1

            report(
                f"Could not find the configured image field ('{image_field}') in the current "
                f"note type ('{note.model()['name']}'), and no fields are available.",
                key=("image_field_missing", nt_id, image_field),
            )
            return None

    if field_names:
        return len(field_names) - 1
    return None


def _network_available() -> bool:
    original_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(_NET_CHECK_TIMEOUT_S)
        for host in _NET_CHECK_HOSTS:
            try:
                socket.gethostbyname(host)
                return True
            except Exception:
                continue
        return False
    finally:
        try:
            socket.setdefaulttimeout(original_timeout)
        except Exception:
            pass


def _infer_suffix_from_url(url: str) -> str:
    try:
        from urllib.parse import urlparse

        path = urlparse(url).path.lower()
        for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
            if path.endswith(ext):
                return ext
    except Exception:
        pass
    return ".jpg"


def _download_bytes(image_url: str, timeout_s: float = 10.0, max_retries: int = 5, backoff_base_s: float = 0.75) -> bytes:
    """
    Download bytes from image_url using a browser-like header set to avoid 403/blocks.
    Retries on transient network errors with exponential backoff.
    """
    req = urllib.request.Request(
        image_url,
        headers={
            "User-Agent": _UA,
            "Accept": _ACCEPT_IMG,
            "Referer": _DEFAULT_REFERER,
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        },
    )
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as response:
                return response.read()
        except (urllib.error.URLError, socket.timeout) as exc:
            last_exc = exc
            if attempt < max_retries:
                time.sleep(backoff_base_s * (2 ** attempt))
                continue
            raise
    # Defensive; the loop above always either returns or raises.
    if last_exc:
        raise last_exc
    raise RuntimeError("download failed without exception")


_SAFE_PREFIX_RE = re.compile(r"[^A-Za-z0-9_-]")


def _safe_prefix(raw: str, default: str = "img_", max_len: int = 32) -> str:
    cleaned = _SAFE_PREFIX_RE.sub("", raw or "")
    cleaned = cleaned[:max_len].strip("_-")
    if not cleaned:
        cleaned = default.rstrip("_")
    return cleaned + "_"


def save_file_to_library(editor, image_url, prefix, suffix):
    """
    Download image_url to a temp file and add it to Anki media.
    Returns (media_filename, error_code) where error_code is one of:
    - None (success)
    - 'offline' (clear offline case)
    - 'network' (timeout/URLError/HTTPError)
    - 'unexpected' (any other exception)
    """
    if not _network_available():
        return None, "offline"

    timeout_s, max_retries, backoff_base_s = get_net_settings()
    safe_prefix = _safe_prefix(prefix)

    temp_path = None
    i_file = None
    try:
        i_file, temp_path = mkstemp(prefix=safe_prefix, suffix=suffix)
        try:
            image_binary = _download_bytes(
                image_url,
                timeout_s=timeout_s,
                max_retries=max_retries,
                backoff_base_s=backoff_base_s,
            )
            os.write(i_file, image_binary)
        finally:
            os.close(i_file)
            i_file = None

        result_filename = _add_file_safely(editor, temp_path)
        return result_filename, None

    except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout):
        return None, "network"

    except Exception as e:
        report(f"Unexpected error while saving image\n\n{repr(e)}\n\n{image_url}")
        return None, "unexpected"
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass


def _add_file_safely(editor, temp_path):
    """
    Add a file to Anki's media collection, preferring a copy semantics so the
    temp file is safe to delete after the call returns. Newer Anki versions
    accept `force_copy`; older versions don't, so we fall back gracefully.
    """
    add_file = editor.mw.col.media.addFile
    try:
        return add_file(temp_path, force_copy=True)
    except TypeError:
        return add_file(temp_path)


def save_image_to_library(editor, image_url):
    """
    Derive a stable filename prefix when possible and pick an extension from the URL.
    Returns (media_filename, error_code) as described in save_file_to_library().
    """
    if not image_url:
        return None, "network"

    prefix = "img_"
    if "id=" in image_url:
        try:
            prefix = image_url.split("id=", 1)[1].split("&", 1)[0] + "_"
        except Exception:
            pass

    suffix = _infer_suffix_from_url(image_url)
    return save_file_to_library(editor, image_url, prefix, suffix)


def image_tag(image_src):
    # Tag marked with class=imgsearch so only add-on images are targeted for replacement
    src = html.escape(str(image_src or ""), quote=True)
    return f'<img src="{src}" class="imgsearch">'
