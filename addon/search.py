# search.py

from anki.utils import strip_html_media
from . import utils

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

    if provider in ("duckduckgo", "ddg"):
        if _get_ddg:
            urls = _get_ddg(q)
            if urls:
                return urls, "DuckDuckGo"
        # Fallback to Yandex when DDG is empty/unavailable
        return _get_yandex(q), "Yandex (fallback from DuckDuckGo)"

    if provider == "google":
        if not getgimages:
            if fallback_on:
                return _get_yandex(q), "Yandex (fallback from Google)"
            return [], "Google"
        urls = getgimages(q)
        if urls:
            return urls, "Google"
        if fallback_on:
            return _get_yandex(q), "Yandex (fallback from Google)"
        return [], "Google"

    return _get_yandex(q), "Yandex"


def get_provider_label(query: str) -> str:
    q = _clean_query(query)
    return PROVIDERS.get(q) or _provider_label_from_config()


def getresultbyquery(query: str) -> str | None:
    q = _clean_query(query)
    if q not in RESULTS or not RESULTS[q]:
        urls, label = _provider_results_and_label(q)
        RESULTS[q] = urls
        INDICES[q] = 0 if urls else -1
        PROVIDERS[q] = label
    _touch_query(q)
    _evict_cache_if_needed()
    return _current_url(q)


def getnextresultbyquery(query: str) -> str | None:
    q = _clean_query(query)
    if q in RESULTS and INDICES.get(q, -1) < len(RESULTS[q]) - 1:
        INDICES[q] += 1
    return _current_url(q)


def getprevresultbyquery(query: str) -> str | None:
    q = _clean_query(query)
    if q in RESULTS and INDICES.get(q, -1) > 0:
        INDICES[q] -= 1
    return _current_url(q)
