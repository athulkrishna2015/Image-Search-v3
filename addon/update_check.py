# update_check.py

from __future__ import annotations

import json
import os
from pathlib import Path

from aqt import mw

from .logger import log
from .tabs import ADDON_PACKAGE


def _addon_dir() -> Path:
    return Path(__file__).resolve().parent


def current_version() -> str:
    """Read the add-on's manifest version (e.g. '3.11.2')."""
    # First try to read from the local addon directory
    manifest = _addon_dir() / "manifest.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return str(data.get("version") or "").strip()
    except Exception as exc:
        log.debug("update_check: manifest read failed from local dir: %r", exc)

    # If that fails, try to get from Anki's addon manager
    try:
        if not mw or not getattr(mw, "addonManager", None):
            return ""
        meta = mw.addonManager.addonMeta(ADDON_PACKAGE)
        if isinstance(meta, dict) and "version" in meta:
            return str(meta["version"]).strip()
    except Exception as exc:
        log.debug("update_check: manifest read failed from addonManager: %r", exc)

    return ""


def _get_meta() -> dict:
    """Read this add-on's `meta.json` (Anki-managed per-install state)."""
    manager_meta = {}
    if ADDON_PACKAGE.isdigit():
        try:
            if mw and getattr(mw, "addonManager", None):
                meta = mw.addonManager.addonMeta(ADDON_PACKAGE) or {}
                if isinstance(meta, dict):
                    manager_meta = meta
        except Exception as exc:
            log.warning("update_check: addonMeta read failed: %r", exc)
    try:
        local_meta = json.loads(
            (_addon_dir() / "meta.json").read_text(encoding="utf-8")
        )
        if isinstance(local_meta, dict):
            return {**local_meta, **manager_meta}
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        log.debug("update_check: local metadata read skipped: %r", exc)
    return manager_meta


def _set_meta(meta: dict) -> None:
    # A source checkout is commonly imported as `addon`, which is not an
    # Anki-registered package. In that environment write the local fallback
    # directly and avoid a misleading addon-manager warning. Installed Anki
    # add-ons use their numeric folder name as the module/package name.
    if ADDON_PACKAGE.isdigit() and mw and getattr(mw, "addonManager", None):
        try:
            mw.addonManager.writeAddonMeta(ADDON_PACKAGE, meta)
            return
        except Exception as exc:
            log.warning("update_check: writeAddonMeta failed: %r", exc)

    try:
        path = _addon_dir() / "meta.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        os.replace(temp_path, path)
    except Exception as exc:
        log.warning("update_check: local metadata write failed: %r", exc)


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
