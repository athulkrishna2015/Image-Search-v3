# search.py

from __future__ import annotations

from anki.utils import strip_html_media
from . import utils
from .logger import log

# Yandex provider: support either export name
try:
    from .yimages import getyimages as _get_yandex  # older file name
except Exception:
    from .yimages import get_yimages as _get_yandex  # newer file name

# Google provider is optional
try:
    from .gimages import getgimages
except Exception:
    getgimages = None

# DuckDuckGo (hidden) provider is optional
try:
    from .ddg_hidden_test import get_ddg_images as _get_ddg
except Exception:
    _get_ddg = None

# Bing provider (keyless) is optional
try:
    from .bing_images import get_bing_images as _get_bing
except Exception:
    _get_bing = None

# Brave Image Search API provider is optional (requires api key)
try:
    from .brave_images import get_brave_images as _get_brave
except Exception:
    _get_brave = None

# Cache of image URL lists per query
RESULTS: dict[str, list[str]] = {}

# Current index per query
INDICES: dict[str, int] = {}

# Provider label per query
PROVIDERS: dict[str, str] = {}

MAX_CACHED_QUERIES = 100


def _clean_query(query: str) -> str:
    return strip_html_media(query)


def _provider_label_from_config() -> str:
    cfg = utils.get_config() or {}
    provider = (cfg.get("provider") or "yandex").lower()
    if provider in ("duckduckgo", "ddg"):
        return "DuckDuckGo"
    if provider == "google":
        return "Google"
    if provider == "bing":
        return "Bing"
    if provider == "brave":
        return "Brave"
    return "Yandex"


def _current_url(q: str) -> str | None:
    if q not in RESULTS or not RESULTS[q]:
        return None
    idx = INDICES.get(q, 0)
    if idx < 0 or idx >= len(RESULTS[q]):
        return None
    return RESULTS[q][idx]


def _touch_query(q: str) -> None:
    if q in RESULTS:
        RESULTS[q] = RESULTS.pop(q)
    if q in INDICES:
        INDICES[q] = INDICES.pop(q)
    if q in PROVIDERS:
        PROVIDERS[q] = PROVIDERS.pop(q)


def _evict_cache_if_needed() -> None:
    while len(RESULTS) > MAX_CACHED_QUERIES:
        oldest_query = next(iter(RESULTS))
        RESULTS.pop(oldest_query, None)
        INDICES.pop(oldest_query, None)
        PROVIDERS.pop(oldest_query, None)


def _provider_results_and_label(q: str) -> tuple[list[str], str]:
    cfg = utils.get_config() or {}
    provider = (cfg.get("provider") or "yandex").lower()
    fallback_on = bool(cfg.get("google_fallback_to_yandex", True))
    log.debug("provider routing: provider=%s fallback=%s query=%r", provider, fallback_on, q)

    if provider == "bing":
        if _get_bing:
            urls = _get_bing(q)
            if urls:
                return urls, "Bing"
        if fallback_on:
            log.info("Bing provider unavailable or empty; falling back to Yandex for %r", q)
            return _get_yandex(q), "Yandex (fallback from Bing)"
        return [], "Bing"

    if provider == "brave":
        if _get_brave:
            urls = _get_brave(q)
            if urls:
                return urls, "Brave"
        if fallback_on:
            log.info("Brave provider unavailable or empty; falling back to Yandex for %r", q)
            return _get_yandex(q), "Yandex (fallback from Brave)"
        return [], "Brave"

    if provider in ("duckduckgo", "ddg"):
        if _get_ddg:
            urls = _get_ddg(q)
            if urls:
                return urls, "DuckDuckGo"
        log.info("DDG provider unavailable or empty; falling back to Yandex for %r", q)
        return _get_yandex(q), "Yandex (fallback from DuckDuckGo)"

    if provider == "google":
        if not getgimages:
            if fallback_on:
                log.info("Google provider not loaded; falling back to Yandex for %r", q)
                return _get_yandex(q), "Yandex (fallback from Google)"
            return [], "Google"
        urls = getgimages(q)
        if urls:
            return urls, "Google"
        if fallback_on:
            log.info("Google returned no results; falling back to Yandex for %r", q)
            return _get_yandex(q), "Yandex (fallback from Google)"
        return [], "Google"

    return _get_yandex(q), "Yandex"


def get_provider_label(query: str) -> str:
    q = _clean_query(query)
    return PROVIDERS.get(q) or _provider_label_from_config()


def getresultbyquery(query: str) -> str | None:
    q = _clean_query(query)
    log.debug("getresultbyquery: query=%r", q)
    if q not in RESULTS or not RESULTS[q]:
        urls, label = _provider_results_and_label(q)
        RESULTS[q] = urls
        INDICES[q] = 0 if urls else -1
        PROVIDERS[q] = label
        log.info("cache miss: query=%r provider=%s count=%d", q, label, len(urls))
    else:
        log.debug("cache hit: query=%r count=%d", q, len(RESULTS[q]))
    _touch_query(q)
    _evict_cache_if_needed()
    return _current_url(q)


def getnextresultbyquery(query: str) -> str | None:
    q = _clean_query(query)
    if q in RESULTS and INDICES.get(q, -1) < len(RESULTS[q]) - 1:
        INDICES[q] += 1
    _touch_query(q)
    return _current_url(q)


def getprevresultbyquery(query: str) -> str | None:
    q = _clean_query(query)
    if q in RESULTS and INDICES.get(q, -1) > 0:
        INDICES[q] -= 1
    _touch_query(q)
    return _current_url(q)
