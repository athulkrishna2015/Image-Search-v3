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

# Cache of image URL lists per query
RESULTS: dict[str, list[str]] = {}

# Current index per query
INDICES: dict[str, int] = {}


def _current_url(q: str) -> str | None:
    if q not in RESULTS or not RESULTS[q]:
        return None
    idx = INDICES.get(q, 0)
    if idx < 0 or idx >= len(RESULTS[q]):
        return None
    return RESULTS[q][idx]


def _provider_results(q: str) -> list[str]:
    cfg = utils.get_config() or {}
    provider = (cfg.get("provider") or "yandex").lower()
    fallback_on = bool(cfg.get("google_fallback_to_yandex", True))

    if provider == "google":
        if not getgimages:
            return _get_yandex(q) if fallback_on else []
        urls = getgimages(q)
        if urls:
            return urls
        return _get_yandex(q) if fallback_on else []

    return _get_yandex(q)


def getresultbyquery(query: str) -> str | None:
    q = strip_html_media(query)
    if q not in RESULTS or not RESULTS[q]:
        RESULTS[q] = _provider_results(q)
        INDICES[q] = 0 if RESULTS[q] else -1
    return _current_url(q)


def getnextresultbyquery(query: str) -> str | None:
    q = strip_html_media(query)
    if q in RESULTS and INDICES.get(q, -1) < len(RESULTS[q]) - 1:
        INDICES[q] += 1
    return _current_url(q)


def getprevresultbyquery(query: str) -> str | None:
    q = strip_html_media(query)
    if q in RESULTS and INDICES.get(q, -1) > 0:
        INDICES[q] -= 1
    return _current_url(q)
