import re
import json
import time
import requests
import urllib.parse

from . import utils

# Silence only SSL warnings for verify=False; keep other warnings
requests.packages.urllib3.disable_warnings()

BASE_URL = "https://yandex.ru/images/search?format=json&request={%22blocks%22:[{%22block%22:%22serp-list_infinite_yes%22,%22params%22:{},%22version%22:2}]}&text="
headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT_S = 8
MAX_RETRIES = 2
BACKOFF_BASE_S = 0.75


def make_yimages_url(query: str) -> str:
    return BASE_URL + urllib.parse.quote_plus(query)


def get_yimages_response(query: str):
    """
    Fetch JSON with retries and timeouts.
    Returns a dict on success, or None on any network/parse failure.
    """
    url = make_yimages_url(query)
    last_err_msg = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            r = requests.get(
                url, headers=headers, timeout=REQUEST_TIMEOUT_S, verify=False
            )
            r.raise_for_status()
            # If Yandex sends non-JSON or HTML on throttling, this will raise
            return r.json()
        except requests.exceptions.Timeout:
            last_err_msg = "Network timeout while contacting Yandex Images."
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFF_BASE_S * (2 ** attempt))
                continue
            utils.report(f"{last_err_msg}\n\n{url}")
            return None
        except requests.exceptions.ConnectionError:
            # Offline, DNS failure, or blocked network
            utils.report(f"Network unavailable or DNS error.\n\n{url}")
            return None
        except requests.exceptions.RequestException as e:
            utils.report(f"Request error\n\n{repr(e)}\n\n{url}")
            return None
        except ValueError as e:
            # JSON decoding error
            utils.report(f"Invalid JSON response\n\n{repr(e)}\n\n{url}")
            return None

    # Should not reach here
    if last_err_msg:
        utils.report(f"{last_err_msg}\n\n{url}")
    return None


def parse_yimages_response(response):
    """
    Parse Yandex Images JSON and extract thumbnail URLs.
    Returns a list of image URLs; returns [] on any issue.
    """
    result = []

    # Guard against None or unexpected types
    if not isinstance(response, dict):
        return result

    try:
        blocks = response.get("blocks")
        if not blocks or not isinstance(blocks, list):
            utils.report("Error parsing json response\n\nKey 'blocks' missing or invalid")
            return result

        block = blocks[0]
        # Some responses may not include the expected structure
        name = block.get("name") or {}
        if not isinstance(name, dict) or name.get("block") != "serp-list_infinite_yes":
            utils.report("Error parsing json response\n\nUnexpected 'name.block' value")
            return result

        html = block.get("html") or ""
        if not html or "data-bem" not in html or "serp-item" not in html:
            utils.report("Error parsing json response\n\nMissing expected HTML markers")
            return result

    except Exception as e:
        utils.report("Error parsing json response\n\n" + repr(e))
        return result

    # Undocumented parsing of Yandex Images response
    # Extract JSON fragments embedded in data-bem for serp items
    # Example attribute: data-bem='{"serp-item":{...}}'
    found = re.findall(r"data-bem='{.serp-item.:(.*?)}'", html)
    for item in (found or []):
        try:
            item_json = json.loads(item)
            thumb = item_json.get("thumb") or {}
            url = thumb.get("url")
            if not url:
                continue
            image_url = "https:" + url.replace("&", "&")
            result.append(image_url)
        except Exception:
            # Skip malformed entries quietly
            continue

    return result


def get_yimages(query: str):
    response = get_yimages_response(query)
    # If response is None (offline, timeout, bad JSON), parse returns []
    return parse_yimages_response(response)
