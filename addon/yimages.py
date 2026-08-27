import re
import json
import time
import requests
import urllib.parse
from aqt import mw

from .logger import log
from .utils import get_net_settings

# No UI or dialogs here; let the caller decide how/when to notify.

BASE_URL = (
    "https://yandex.ru/images/search?"
    "format=json&request={%22blocks%22:[{%22block%22:%22serp-list_infinite_yes%22,"
    "%22params%22:{},%22version%22:2}]}&text="
)

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


def make_yimages_url(query: str) -> str:
    return BASE_URL + urllib.parse.quote_plus(query)

def get_yimages_response(query: str):
    """
    Returns parsed JSON dict on success, or None on any error.
    Never shows UI notifications; callers decide how/when to notify.
    """
    timeout_s, max_retries, backoff_base_s = get_net_settings()
    url = make_yimages_url(query)
    log.debug("yimages: request query=%r timeout=%.1fs retries=%d", query, timeout_s, max_retries)

    for attempt in range(max_retries + 1):
        try:
            r = requests.get(url, headers=headers, timeout=timeout_s)
            r.raise_for_status()
            data = r.json()
            log.info("yimages: ok query=%r status=%s bytes=%s", query, r.status_code, len(r.content))
            return data
        except requests.exceptions.Timeout:
            log.warning("yimages: timeout query=%r attempt=%d/%d", query, attempt, max_retries)
            if attempt < max_retries:
                time.sleep(backoff_base_s * (2 ** attempt))
                continue
            return None
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.RequestException,
            ValueError,
        ) as exc:
            log.warning("yimages: giving up query=%r err=%r", query, exc)
            return None

    return None

def parse_yimages_response(response):
    """
    Returns a list of image URLs on success, or an empty list if
    response is invalid, empty, or cannot be parsed.
    Never shows UI notifications; callers decide how/when to notify.
    """
    result = []
    if not isinstance(response, dict):
        return result

    try:
        blocks = response.get("blocks")
        if not blocks or not isinstance(blocks, list):
            return result

        block = blocks[0]
        html_str = block.get("html") or ""
        if not html_str or "data-bem" not in html_str or "serp-item" not in html_str:
            return result
    except Exception:
        return result

    # Extract URLs from inline JSON in data-bem attributes.
    # Yandex has used both ' and " as attribute delimiters; accept both.
    pattern = re.compile(r"""data-bem=(['"])(\{.*?serp-item.*?\})\1""", re.DOTALL)
    for m in pattern.finditer(html_str):
        raw = m.group(2)
        # Normalize single-quoted JSON to double-quoted for json.loads.
        if raw.startswith("'") and raw.endswith("'"):
            raw = '"' + raw[1:-1].replace('"', '\\"') + '"'
        try:
            item_json = json.loads(raw)
        except Exception:
            continue
        # The captured snippet is wrapped as {"serp-item":{...}}. The
        # actual image fields (thumb, href, ...) live inside the nested
        # "serp-item" object. Fall back to the outer dict for older
        # Yandex payloads where the snippet might be a flat object.
        nested = item_json.get("serp-item")
        if isinstance(nested, dict):
            inner = nested
        elif isinstance(item_json, dict):
            inner = item_json
        else:
            continue
        thumb = inner.get("thumb") or {}
        url = thumb.get("url")
        if not url:
            continue
        image_url = "https:" + url if url.startswith("//") else url
        result.append(image_url)

    return result

def get_yimages(query: str):
    response = get_yimages_response(query)
    urls = parse_yimages_response(response)
    log.debug("yimages: parsed query=%r urls=%d", query, len(urls))
    return urls
