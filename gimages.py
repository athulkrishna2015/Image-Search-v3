# gimages.py
import time
import requests
from aqt import mw

# Keep requests quiet in Anki’s console
try:
    requests.packages.urllib3.disable_warnings()
except Exception:
    pass


def _get_net_settings():
    try:
        cfg = mw.addonManager.getConfig(__name__) or {}
    except Exception:
        cfg = {}
    timeout_s = float(cfg.get("request_timeout_s", 10.0))
    max_retries = int(cfg.get("max_retries", 5))
    backoff_base_s = float(cfg.get("backoff_base_s", 0.75))
    return timeout_s, max_retries, backoff_base_s


def _get_google_creds():
    try:
        cfg = mw.addonManager.getConfig(__name__) or {}
    except Exception:
        cfg = {}
    return (cfg.get("google_api_key") or "").strip(), (cfg.get("google_cx") or "").strip()


def get_gimages(query: str):
    """
    Returns a list of direct image URLs using Google Custom Search JSON API.
    If credentials are missing or a request fails, returns [].
    """
    api_key, cx = _get_google_creds()
    if not api_key or not cx:
        return []

    timeout_s, max_retries, backoff_base_s = _get_net_settings()

    base = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "searchType": "image",
        "safe": "active",
        "num": 10,  # up to 10 per page for the JSON API
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
