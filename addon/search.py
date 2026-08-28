# search.py

from __future__ import annotations

from anki.utils import strip_html_media
from . import utils
from .logger import log

# All providers share the same retry/timeout config and routing
# code. The active one is chosen by the `provider` config key.
#
# Labels in the UI distinguish "official" providers (which use
# first-party APIs and require keys) from "unofficial" providers
# (which use undocumented public endpoints and don't need keys).
#
# Per-provider fallback chains are configurable: each provider has
# `fallback_<key>` config (list of provider keys in fallback order,
# or a single string for backwards compat). The default chains put
# the most reliable unofficial provider (Yandex public) last so
# every chain ultimately reaches it.

# Public, in the sense that the UI may show them by default.
_PROVIDER_KEYS = ("yandex", "yandex_official", "bing", "duckduckgo", "brave", "google")

# Default fallback chain for each primary provider. Each chain is
# the list of provider keys tried in order if the primary returns
# no results. The last entry is always a keyless unofficial provider
# so the chain never ends in mid-air.
DEFAULT_FALLBACKS = {
    "yandex":          ("bing", "duckduckgo"),
    "yandex_official": ("yandex", "bing", "duckduckgo"),
    "bing":            ("yandex", "duckduckgo"),
    "duckduckgo":      ("yandex", "bing"),
    "brave":           ("yandex", "bing", "duckduckgo"),
    "google":          ("yandex", "bing", "duckduckgo"),
}

# Human labels (used for tooltips and routing log messages).
_PROVIDER_LABELS = {
    "yandex":          "Yandex (unofficial)",
    "yandex_official": "Yandex (Official API)",
    "bing":            "Bing (unofficial)",
    "duckduckgo":      "DuckDuckGo (unofficial)",
    "brave":           "Brave",
    "google":          "Google",
}

# Resolver table: each provider key -> a zero-arg callable that
# returns the image-search function. We import lazily so the add-on
# still loads if one provider fails to import (the user will simply
# see that provider's chain fall through).
def _load_yimages():
    from .yimages import get_yimages
    return get_yimages

def _load_gimages():
    from .gimages import getgimages
    return getgimages

def _load_ddg():
    from .ddg_hidden_test import get_ddg_images
    return get_ddg_images

def _load_bing():
    from .bing_images import get_bing_images
    return get_bing_images

def _load_brave():
    from .brave_images import get_brave_images
    return get_brave_images

def _load_yandex_official():
    from .yandex_official import get_yandex_official_images
    return get_yandex_official_images


# Map provider key -> loader. Loaders never raise; they import the
# provider module and return its image-search callable.
_PROVIDER_LOADERS = {
    "yandex":          _load_yimages,
    "yandex_official": _load_yandex_official,
    "bing":            _load_bing,
    "duckduckgo":      _load_ddg,
    "brave":           _load_brave,
    "google":          _load_gimages,
}

# Cache of resolved callables so each import only happens once.
_RESOLVER_CACHE: dict[str, object] = {}


def _provider_callable(key: str):
    """
    Return the image-search callable for a provider key, or None
    if the module is unavailable. Resolved callables are cached.
    """
    if key in _RESOLVER_CACHE:
        return _RESOLVER_CACHE[key] or None
    loader = _PROVIDER_LOADERS.get(key)
    if loader is None:
        return None
    try:
        fn = loader()
    except Exception as exc:
        log.warning("provider %r loader failed: %r", key, exc)
        _RESOLVER_CACHE[key] = None
        return None
    _RESOLVER_CACHE[key] = fn
    return fn


def _label_for(key: str) -> str:
    return _PROVIDER_LABELS.get(key, key)


def _normalize_provider(key: str) -> str:
    """Accept "ddg" as an alias for "duckduckgo" so old configs still
    work. Other keys are returned as-is."""
    if key in ("ddg",):
        return "duckduckgo"
    return key


def _resolve_fallbacks(cfg: dict, primary: str) -> list[str]:
    """
    Return the configured fallback chain for `primary`, as a list
    of provider keys, with `primary` always at the front. Accepts
    both a list (`fallback_yandex: ["bing", "ddg"]`) and the legacy
    single string (`fallback_yandex: "bing"`). Falls back to
    DEFAULT_FALLBACKS when unset / empty.

    The primary is always tried first; the configured list is
    treated as the FALLBACK chain only, never the primary's position.
    """
    primary = _normalize_provider(primary)
    key = f"fallback_{primary}"
    value = cfg.get(key)
    
    # Check for explicit empty list (meaning no fallbacks)
    if value == []:
        return [primary]
    
    if value is None or value == "":
        fallback = list(DEFAULT_FALLBACKS.get(primary, ()))
    elif isinstance(value, str):
        fallback = [_normalize_provider(value)]
    elif isinstance(value, (list, tuple)):
        fallback = [_normalize_provider(v) for v in value
                    if isinstance(v, str) and _normalize_provider(v) != primary]
    else:
        fallback = list(DEFAULT_FALLBACKS.get(primary, ()))

    # Always lead with the primary.
    return [primary] + [k for k in fallback if k != primary]


def _provider_label_from_config() -> str:
    cfg = utils.get_config() or {}
    provider = _normalize_provider((cfg.get("provider") or "yandex").lower())
    return _label_for(provider)

# Cache of image URL lists per query
RESULTS: dict[str, list[str]] = {}

# Current index per query
INDICES: dict[str, int] = {}

# Provider label per query
PROVIDERS: dict[str, str] = {}

MAX_CACHED_QUERIES = 100


def _clean_query(query: str) -> str:
    return strip_html_media(query)


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


def _try_providers_in_order(
    chain: list[str], q: str, primary: str, primary_label: str
) -> tuple[list[str], str]:
    """
    Walk `chain` (already containing the primary at index 0). For
    each key in order, call its resolver; the first to return a
    non-empty URL list wins. The returned label is the primary's
    label for the primary result, or "X (fallback for Y)" for
    fallback results.

    Returns ([], last_label) when no provider returns results.
    """
    last_label = primary_label
    for key in chain:
        resolver = _provider_callable(key)
        if resolver is None:
            log.info("provider %r resolver not available; skipping", key)
            continue
        try:
            urls = resolver(q)
        except Exception as exc:
            log.warning("provider %r raised: %r", key, exc)
            urls = []
        label = _label_for(key)
        if urls:
            if key == primary:
                return urls, label
            return urls, f"{label} (fallback for {primary_label})"
        last_label = label
    return [], last_label


def _provider_results_and_label(q: str) -> tuple[list[str], str]:
    cfg = utils.get_config() or {}
    provider = _normalize_provider((cfg.get("provider") or "yandex").lower())
    primary_label = _label_for(provider)
    chain = _resolve_fallbacks(cfg, provider)
    log.debug(
        "provider routing: primary=%s chain=%s query=%r",
        provider, chain, q,
    )
    return _try_providers_in_order(chain, q, provider, primary_label)


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


def clear_cache() -> None:
    """
    Drop all in-memory cached results. Called from the settings
    dialog when the user Saves, so that a provider / query-field /
    image-field change takes effect on the next search instead of
    serving stale results from before the change.
    """
    RESULTS.clear()
    INDICES.clear()
    PROVIDERS.clear()