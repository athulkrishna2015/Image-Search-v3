# yandex_official.py

"""
Official Yandex Search API v2 (Image Search by text).

Reference (from the official Yandex AI Studio docs):

    POST https://searchapi.api.cloud.yandex.net/v2/image/search
    Authorization: Api-Key <API_key>          (or: Bearer <IAM_token>)
    Content-Type: application/json

    {
      "query": {
        "searchType": "ru" | "tr" | "com" | "kk" | "uz" | "by",
        "queryText": "<search query>",
        "familyMode": "moderate" | "strict" | "none",
        "page": "0",
        "fixTypoMode": "on" | "off"
      },
      "imageSpec": {
        "format":  "any" | "jpeg" | "gif" | "png",
        "size":    "any" | "small" | "medium" | "large" | "wallpaper" | "enormous",
        "orientation": "any" | "vertical" | "horizontal" | "square",
        "color":   "any" | "color" | "gray" | "red" | "orange" | "yellow"
                  | "green" | "cyan" | "blue" | "violet" | "white" | "black"
      },
      "site":     "<optional site restriction>",
      "docsOnPage": "5",                  (1..100)
      "folderId":  "<Yandex Cloud folder>",
      "userAgent": "<optional User-Agent string>"
    }

Response:

    {
      "rawData": "<base64-encoded XML>"
    }

The XML follows the legacy Yandex XML schema. Image URLs live at
    response/results/grouping/group/doc/properties/img/image-doc/image-shown/url
with thumbnails under
    response/results/grouping/group/doc/properties/img/image-doc/thumbnails/thumbnail[@url]

This module:
- builds and POSTs the request body,
- retries with the shared backoff on transient failures,
- decodes the base64 wrapper,
- parses the XML and pulls out the original image URLs.
"""

from __future__ import annotations

import base64
import time
from typing import Optional
from xml.etree import ElementTree as ET

from aqt import mw

from .logger import log
from .utils import get_net_settings


_API_URL = "https://searchapi.api.cloud.yandex.net/v2/image/search"
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
)

_SEARCH_TYPES = ("ru", "tr", "com", "kk", "uz", "by")
_FAMILY_MODES = ("none", "moderate", "strict")


def _get_creds() -> tuple[str, str]:
    """Return (api_key, folder_id) from the add-on config."""
    try:
        cfg = mw.addonManager.getConfig(__name__) or {}
    except Exception:
        cfg = {}
    return (
        (cfg.get("yandex_api_key") or "").strip(),
        (cfg.get("yandex_folder_id") or "").strip(),
    )


def _coerce(value: str, allowed: tuple, default: str) -> str:
    if value in allowed:
        return value
    return default


def _build_payload(query: str) -> dict:
    """Build the JSON body for the text-to-image search query."""
    api_key, folder_id = _get_creds()
    try:
        cfg = mw.addonManager.getConfig(__name__) or {}
    except Exception:
        cfg = {}
    search_type = _coerce(
        (cfg.get("yandex_official_search_type") or "com").lower(),
        _SEARCH_TYPES, "com",
    )
    family_mode = _coerce(
        (cfg.get("yandex_official_family_mode") or "moderate").lower(),
        _FAMILY_MODES, "moderate",
    )
    return {
        "query": {
            "searchType": search_type,
            "queryText": query,
            "familyMode": family_mode,
            "page": "0",
            "fixTypoMode": "on",
        },
        "imageSpec": {
            "format": "any",
            "size": "any",
            "orientation": "any",
            "color": "any",
        },
        "docsOnPage": "20",
        "folderId": folder_id,
        "userAgent": _USER_AGENT,
    }


def get_yandex_official_images(query: str) -> list[str]:
    """
    Return a list of image URLs for `query` using the official Yandex
    Search API, or [] on any error / missing key / folder id.

    The first 20 image URLs are returned (the API's docsOnPage cap we
    use). The list order matches the original search results.
    """
    query = (query or "").strip()
    if not query:
        return []

    api_key, folder_id = _get_creds()
    if not api_key or not folder_id:
        log.info(
            "yandex_official: missing api_key or folder_id; returning []"
        )
        return []

    timeout_s, max_retries, backoff_base_s = get_net_settings()
    import requests

    headers = {
        "Authorization": f"Api-Key {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = _build_payload(query)
    log.debug(
        "yandex_official: request query=%r folder_id=%r timeout=%.1fs retries=%d",
        query, folder_id, timeout_s, max_retries,
    )

    response_json = None
    for attempt in range(max_retries + 1):
        try:
            r = requests.post(
                _API_URL, headers=headers, json=body, timeout=timeout_s
            )
            r.raise_for_status()
            response_json = r.json()
            log.info(
                "yandex_official: ok query=%r status=%s bytes=%s",
                query, r.status_code, len(r.content),
            )
            break
        except requests.exceptions.Timeout:
            log.warning(
                "yandex_official: timeout query=%r attempt=%d/%d",
                query, attempt, max_retries,
            )
            if attempt < max_retries:
                time.sleep(backoff_base_s * (2 ** attempt))
                continue
            return []
        except Exception as exc:
            log.warning(
                "yandex_official: giving up query=%r err=%r",
                query, exc,
            )
            return []

    if not isinstance(response_json, dict):
        return []

    raw = response_json.get("rawData")
    if not isinstance(raw, str) or not raw:
        return []

    return parse_yandex_official_response(raw)


def parse_yandex_official_response(raw_data_b64: str) -> list[str]:
    """
    Decode the base64 wrapper, parse the XML, and return a list of
    image URLs (original / image-shown), deduped while preserving
    order. Returns [] on any structural mismatch.
    """
    if not isinstance(raw_data_b64, str) or not raw_data_b64:
        return []
    try:
        xml_bytes = base64.b64decode(raw_data_b64, validate=False)
    except Exception as exc:
        log.warning("yandex_official: b64 decode failed: %r", exc)
        return []

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        log.warning("yandex_official: XML parse failed: %r", exc)
        return []

    urls: list[str] = []
    seen: set[str] = set()
    for url in _iter_image_urls(root):
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def _iter_image_urls(root: ET.Element):
    """
    Walk the Yandex XML response and yield the image URL of every
    `image-shown` element. The path inside a `<group>` is:
        .../doc/properties/img/image-doc/image-shown/url
    """
    for node in root.iter("image-shown"):
        url_el = node.find("url")
        if url_el is None or not url_el.text:
            continue
        yield _normalize(url_el.text)


def _normalize(url: str) -> str:
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    return url


# Backwards-compatible alias matching the original yimages naming.
getyandexofficial = get_yandex_official_images
parse_yandex_official = parse_yandex_official_response
