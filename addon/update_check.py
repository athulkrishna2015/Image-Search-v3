# update_check.py

from __future__ import annotations

import json
from pathlib import Path

from aqt import mw

from .logger import log
from .tabs import ADDON_PACKAGE


def _addon_dir() -> Path:
    return Path(__file__).resolve().parent


def current_version() -> str:
    """Read the add-on's manifest version (e.g. '3.11.2')."""
    manifest = _addon_dir() / "manifest.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("update_check: manifest read failed: %r", exc)
        return ""
    return str(data.get("version") or "").strip()


def _get_meta() -> dict:
    """Read this add-on's `meta.json` (Anki-managed per-install state)."""
    if not mw or not getattr(mw, "addonManager", None):
        return {}
    try:
        meta = mw.addonManager.addonMeta(ADDON_PACKAGE) or {}
        return meta if isinstance(meta, dict) else {}
    except Exception as exc:
        log.warning("update_check: addonMeta read failed: %r", exc)
        return {}


def _set_meta(meta: dict) -> None:
    if not mw or not getattr(mw, "addonManager", None):
        return
    try:
        mw.addonManager.writeAddonMeta(ADDON_PACKAGE, meta)
    except Exception as exc:
        log.warning("update_check: writeAddonMeta failed: %r", exc)


def should_show_support_welcome(config: dict | None) -> bool:
    """
    Return True exactly once per version bump, when the user opens the
    settings dialog. Subsequent opens return False until the version
    changes again. Respects the user's preferences:

      - config['auto_show_support_on_update'] = False  -> never show
      - meta['supporter_opt_out']           = True   -> never show

    The check is intentionally cheap (a couple of dict lookups); it only
    runs when the user opens the settings dialog, never at Anki startup
    or add-on import.
    """
    cfg = config or {}
    if not cfg.get("auto_show_support_on_update", True):
        return False

    meta = _get_meta()
    if meta.get("supporter_opt_out", False):
        return False

    last_seen = str(meta.get("last_support_welcome_version") or "").strip()
    current = current_version()
    if not current:
        return False
    return last_seen != current


def mark_support_welcomed() -> None:
    """Persist the current version as 'last seen' so we don't pop again."""
    meta = _get_meta()
    current = current_version()
    if not current:
        return
    meta["last_support_welcome_version"] = current
    _set_meta(meta)
