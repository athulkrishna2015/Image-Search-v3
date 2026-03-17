# ddg_hidden_test.py

import re
import time
import requests
from aqt import mw

# DuckDuckGo image search via the hidden i.js endpoint.
# This is undocumented and may change; keep it best-effort and quiet.

_DDG_SEARCH_URL = "https://duckduckgo.com/"
_DDG_IMAGE_API_URL = "https://duckduckgo.com/i.js"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://duckduckgo.com/",
    "Origin": "https://duckduckgo.com",
}


def _safe_float(value, default, minimum=None, maximum=None):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = float(default)
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def _safe_int(value, default, minimum=None, maximum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def _get_net_settings():
    try:
        cfg = mw.addonManager.getConfig(__name__) or {}
    except Exception:
        cfg = {}
    timeout_s = _safe_float(cfg.get("request_timeout_s", 10.0), 10.0, minimum=1.0, maximum=120.0)
    max_retries = _safe_int(cfg.get("max_retries", 5), 5, minimum=0, maximum=10)
    backoff_base_s = _safe_float(cfg.get("backoff_base_s", 0.75), 0.75, minimum=0.05, maximum=10.0)
    return timeout_s, max_retries, backoff_base_s


def _request_with_retry(url, params, timeout_s, max_retries, backoff_base_s):
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(url, params=params, headers=_HEADERS, timeout=timeout_s)
            resp.raise_for_status()
            return resp
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                time.sleep(backoff_base_s * (2 ** attempt))
                continue
            return None
        except requests.exceptions.RequestException:
            return None
    return None


def _get_vqd(query: str, timeout_s: float, max_retries: int, backoff_base_s: float) -> str | None:
    resp = _request_with_retry(
        _DDG_SEARCH_URL,
        params={"q": query},
        timeout_s=timeout_s,
        max_retries=max_retries,
        backoff_base_s=backoff_base_s,
    )
    if not resp:
        return None

    match = re.search(r"vqd=['\"]?([^'\"\s]+)", resp.text)
    if not match:
        return None
    return match.group(1)


def get_ddg_images(query: str) -> list[str]:
    query = (query or "").strip()
    if not query:
        return []

    timeout_s, max_retries, backoff_base_s = _get_net_settings()
    vqd = _get_vqd(query, timeout_s, max_retries, backoff_base_s)
    if not vqd:
        return []

    resp = _request_with_retry(
        _DDG_IMAGE_API_URL,
        params={
            "q": query,
            "vqd": vqd,
            "o": "json",
        },
        timeout_s=timeout_s,
        max_retries=max_retries,
        backoff_base_s=backoff_base_s,
    )
    if not resp:
        return []

    try:
        data = resp.json()
    except Exception:
        return []

    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        return []

    urls = []
    for item in results:
        if not isinstance(item, dict):
            continue
        url = item.get("image")
        if url:
            urls.append(url)
    return urls


# Backwards-compatible export name
getddgimages = get_ddg_images


if __name__ == "__main__":
    keyword = "nebula"
    print(f"Searching for: {keyword}...")
    urls = get_ddg_images(keyword)
    print(f"Found {len(urls)} images. Top 5 URLs:")
    for url in urls[:5]:
        print(f"-> {url}")
