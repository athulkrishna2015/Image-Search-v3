# brave_images.py

"""
Brave Image Search via the documented REST API.

Requires a Brave Search API subscription token. Users enter it under
Tools -> Image Search v3 Settings -> Network as `brave_api_key`.

The API returns a JSON payload with up to `count` (default 50,
max 200) image results. Each result includes `properties.url`
(the original image URL), `thumbnail.src` (a 500px Brave-proxied
thumbnail), and `url` (the page that hosts the image).

We prefer `properties.url` and fall back to `thumbnail.src` when
the original is missing. `url` is intentionally NOT used as a
fallback because it is the page URL, not the image URL.
"""

from __future__ import annotations

import time

from aqt import mw

from .logger import log
from .utils import get_net_settings


_BRAVE_URL = "https://api.search.brave.com/res/v1/images/search"
_COUNT = 50
_SAFESEARCH = "strict"


def _get_brave_creds() -> str:
    try:
        cfg = mw.addonManager.getConfig(__name__) or {}
    except Exception:
        cfg = {}
    return (cfg.get("brave_api_key") or "").strip()


def get_brave_images(query: str) -> list[str]:
    """
    Return a list of image URLs for `query`, or [] on any error
    (missing key, network failure, 4xx, 5xx, or empty results).
    """
    query = (query or "").strip()
    if not query:
        return []

    api_key = _get_brave_creds()
    if not api_key:
        log.info("brave_images: missing brave_api_key; returning []")
        return []

    timeout_s, max_retries, backoff_base_s = get_net_settings()
    import requests

    params = {
        "q": query,
        "count": _COUNT,
        "safesearch": _SAFESEARCH,
    }
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }
    log.debug(
        "brave_images: request query=%r timeout=%.1fs retries=%d",
        query, timeout_s, max_retries,
    )

    for attempt in range(max_retries + 1):
        try:
            r = requests.get(
                _BRAVE_URL, params=params, headers=headers, timeout=timeout_s
            )
            r.raise_for_status()
            data = r.json()
            log.info(
                "brave_images: ok query=%r status=%s bytes=%s",
                query, r.status_code, len(r.content),
            )
            break
        except requests.exceptions.Timeout:
            log.warning(
                "brave_images: timeout query=%r attempt=%d/%d",
                query, attempt, max_retries,
            )
            if attempt < max_retries:
                time.sleep(backoff_base_s * (2 ** attempt))
                continue
            return []
        except Exception as exc:
            log.warning("brave_images: giving up query=%r err=%r", query, exc)
            return []

    return parse_brave_response(data)


def parse_brave_response(data) -> list[str]:
    """
    Walk a Brave image-search response and return a list of absolute
    image URLs, deduped while preserving order. Returns [] on any
    structural mismatch.
    """
    if not isinstance(data, dict):
        return []
    results = data.get("results")
    if not isinstance(results, list):
        return []

    urls: list[str] = []
    seen: set[str] = set()
    for item in results:
        if not isinstance(item, dict):
            continue
        # Prefer the original (non-proxied) image URL.
        url: str | None = None
        props = item.get("properties")
        if isinstance(props, dict):
            url = props.get("url")
        if not url:
            thumb = item.get("thumbnail")
            if isinstance(thumb, dict):
                url = thumb.get("src")
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)

    return urls
