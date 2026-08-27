# gimages.py

import time
import requests

from .utils import get_net_settings


def _get_google_creds():
    try:
        from aqt import mw
        cfg = mw.addonManager.getConfig(__name__) or {}
    except Exception:
        cfg = {}
    return (cfg.get("google_api_key") or "").strip(), (cfg.get("google_cx") or "").strip()

def getgimages(query: str):
    """
    Returns a list of direct image URLs using Google Custom Search JSON API.
    If credentials are missing or a request fails, returns [].
    """
    api_key, cx = _get_google_creds()
    if not api_key or not cx:
        return []

    timeout_s, max_retries, backoff_base_s = get_net_settings()
    base = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "searchType": "image",
        "safe": "active",
        "num": 10,  # API limit per request
    }

    for attempt in range(max_retries + 1):
        try:
            r = requests.get(base, params=params, timeout=timeout_s)
            r.raise_for_status()
            data = r.json()
            items = data.get("items") or []
            return [it.get("link") for it in items if it.get("link")]
        except requests.exceptions.Timeout:
            # backoff and retry
            if attempt < max_retries:
                time.sleep(backoff_base_s * (2 ** attempt))
                continue
            return []
        except Exception:
            # quota errors, bad key/cx, etc.
            return []
    return []
