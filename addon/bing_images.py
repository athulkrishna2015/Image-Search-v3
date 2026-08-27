# bing_images.py

"""
Bing Images via the undocumented `/images/async` endpoint.

No API key required. Returns the first ~45 image URLs in the SERP
for a given query. The endpoint is publicly reachable but Bing does
not document it and may rate-limit aggressive clients; the add-on's
shared retry/backoff configuration is reused.
"""

from __future__ import annotations

import html
import re
from urllib.parse import quote_plus

from .logger import log
from .utils import get_net_settings


_BING_URL = "https://www.bing.com/images/async"

# Linux UA. The Bing async endpoint has been observed to 403 / return
# a JS-only page for some Windows-only UAs; a modern Linux Chrome UA
# works reliably.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.bing.com/",
}

# Each murl is wrapped as &quot;...&quot; in the rendered HTML; capture
# the URL between the entities.
_MURL_RE = re.compile(
    r'&quot;murl&quot;:&quot;(https?://[^&]+?)&quot;'
)


def get_bing_images(query: str) -> list[str]:
    """
    Return a list of direct image URLs for `query`, or [] on any
    error. No API key required.
    """
    query = (query or "").strip()
    if not query:
        return []

    timeout_s, max_retries, backoff_base_s = get_net_settings()
    import time
    import requests

    url = f"{_BING_URL}?q={quote_plus(query)}&first=1&count=20"
    log.debug("bing_images: request query=%r timeout=%.1fs retries=%d",
              query, timeout_s, max_retries)

    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            r = requests.get(url, headers=_HEADERS, timeout=timeout_s)
            r.raise_for_status()
            break
        except Exception as exc:
            last_exc = exc
            log.warning("bing_images: attempt %d/%d failed: %r",
                        attempt, max_retries, exc)
            if attempt < max_retries:
                time.sleep(backoff_base_s * (2 ** attempt))
                continue
            return []

    try:
        text = r.text
    except Exception as exc:
        log.warning("bing_images: read failed: %r", exc)
        return []

    # murls are HTML-escaped, so decode them.
    urls: list[str] = []
    seen: set[str] = set()
    for raw in _MURL_RE.findall(text):
        try:
            url = html.unescape(raw)
        except Exception:
            url = raw
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)

    log.info("bing_images: ok query=%r count=%d", query, len(urls))
    return urls
