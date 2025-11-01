import re
import json
import time
import requests
import urllib.parse
from aqt import mw

# Do not show UI here; UI decides how/when to notify.

requests.packages.urllib3.disable_warnings()

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

def _get_net_settings():
    """
    Read network settings from the add-on config with safe fallbacks.
    Keys:
      - request_timeout_s (float, s)
      - max_retries (int)
      - backoff_base_s (float, s)
    """
    try:
        cfg = mw.addonManager.getConfig(__name__) or {}
    except Exception:
        cfg = {}
    timeout_s = float(cfg.get("request_timeout_s", 10.0))
    max_retries = int(cfg.get("max_retries", 5))
    backoff_base_s = float(cfg.get("backoff_base_s", 0.75))
    return timeout_s, max_retries, backoff_base_s

def make_yimages_url(query: str) -> str:
    return BASE_URL + urllib.parse.quote_plus(query)

def get_yimages_response(query: str):
    """
    Returns parsed JSON dict on success, or None on any error.
    Never shows UI notifications; callers decide how/when to notify.
    """
    timeout_s, max_retries, backoff_base_s = _get_net_settings()
    url = make_yimages_url(query)

    for attempt in range(max_retries + 1):
        try:
            r = requests.get(url, headers=headers, timeout=timeout_s, verify=False)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                time.sleep(backoff_base_s * (2 ** attempt))
                continue
            return None
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.RequestException,
            ValueError,
        ):
            # Connection issue, HTTP error, or invalid JSON
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
        name = block.get("name") or {}
        if not isinstance(name, dict) or name.get("block") != "serp-list_infinite_yes":
            return result

        html = block.get("html") or ""
        if not html or "data-bem" not in html or "serp-item" not in html:
            return result
    except Exception:
        # Silent parse errors; return empty list
        return result

    found = re.findall(r"data-bem='{.*?serp-item.*?:(.*?)}'", html)
    for item in (found or []):
        try:
            item_json = json.loads(item)
            thumb = item_json.get("thumb") or {}
            url = thumb.get("url")
            if not url:
                continue
            image_url = "https:" + url
            result.append(image_url)
        except Exception:
            continue

    return result

def get_yimages(query: str):
    response = get_yimages_response(query)
    return parse_yimages_response(response)
