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

_SEARCH_TYPES = {
    "ru": "SEARCH_TYPE_RU",
    "tr": "SEARCH_TYPE_TR",
    "com": "SEARCH_TYPE_COM",
    "kk": "SEARCH_TYPE_KK",
    "uz": "SEARCH_TYPE_UZ",
    "by": "SEARCH_TYPE_BY",
}
_FAMILY_MODES = {
    "none": "FAMILY_MODE_NONE",
    "moderate": "FAMILY_MODE_MODERATE",
    "strict": "FAMILY_MODE_STRICT",
}
_IMAGE_SPEC = {
    "orientation": {
        # The Yandex ImageSpec has no "ANY" orientation. The docs use
        # VERTICAL by default; users can switch via config.
        "any": "IMAGE_ORIENTATION_VERTICAL",
        "vertical": "IMAGE_ORIENTATION_VERTICAL",
        "horizontal": "IMAGE_ORIENTATION_HORIZONTAL",
        "square": "IMAGE_ORIENTATION_SQUARE",
    },
    "color": {
        # The Yandex API has no "ANY" color value; the closest
        # default is IMAGE_COLOR_COLOR (any non-grayscale).
        "any": "IMAGE_COLOR_COLOR",
        "color": "IMAGE_COLOR_COLOR",
        "gray": "IMAGE_COLOR_GRAY",
        "grey": "IMAGE_COLOR_GRAY",
        "red": "IMAGE_COLOR_RED",
        "orange": "IMAGE_COLOR_ORANGE",
        "yellow": "IMAGE_COLOR_YELLOW",
        "green": "IMAGE_COLOR_GREEN",
        "cyan": "IMAGE_COLOR_CYAN",
        "blue": "IMAGE_COLOR_BLUE",
        "violet": "IMAGE_COLOR_VIOLET",
        "white": "IMAGE_COLOR_WHITE",
        "black": "IMAGE_COLOR_BLACK",
    },
    "format": {
        # No ANY for format. JPEG is the docs' default.
        "any": "IMAGE_FORMAT_JPEG",
        "jpeg": "IMAGE_FORMAT_JPEG",
        "png": "IMAGE_FORMAT_PNG",
        "gif": "IMAGE_FORMAT_GIF",
    },
    "size": {
        # No ANY for size. MEDIUM is the docs' default.
        "any": "IMAGE_SIZE_MEDIUM",
        "small": "IMAGE_SIZE_SMALL",
        "medium": "IMAGE_SIZE_MEDIUM",
        "large": "IMAGE_SIZE_LARGE",
        "wallpaper": "IMAGE_SIZE_WALLPAPER",
        "enormous": "IMAGE_SIZE_ENORMOUS",
    },
}


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


def _coerce_enum(value, mapping, default):
    if not value:
        return default
    raw = str(value).strip()
    if not raw:
        return default
    # Already a full prefix form?
    for v in mapping.values():
        if raw == v:
            return v
    # Short form.
    return mapping.get(raw.lower(), default)


def _build_payload(query: str) -> dict:
    """
    Build the JSON body for the text-to-image search query.

    The Yandex Search API v2 uses gRPC-style snake_case field names
    with ALL_CAPS prefix enums (FIX_TYPO_MODE_OFF,
    IMAGE_ORIENTATION_VERTICAL, etc.). We accept user-friendly
    short forms in the config and translate them here.
    """
    try:
        cfg = mw.addonManager.getConfig(__name__) or {}
    except Exception:
        cfg = {}
    return {
        "query": {
            "search_type": _coerce_enum(
                cfg.get("yandex_official_search_type"),
                _SEARCH_TYPES, "SEARCH_TYPE_COM",
            ),
            "query_text": query,
            "family_mode": _coerce_enum(
                cfg.get("yandex_official_family_mode"),
                _FAMILY_MODES, "FAMILY_MODE_MODERATE",
            ),
            "page": "0",
            "fix_typo_mode": "FIX_TYPO_MODE_OFF",
        },
        "image_spec": {
            "format": _coerce_enum(
                cfg.get("yandex_official_format"),
                _IMAGE_SPEC["format"], "IMAGE_FORMAT_JPEG",
            ),
            "size": _coerce_enum(
                cfg.get("yandex_official_size"),
                _IMAGE_SPEC["size"], "IMAGE_SIZE_MEDIUM",
            ),
            "orientation": _coerce_enum(
                cfg.get("yandex_official_orientation"),
                _IMAGE_SPEC["orientation"], "IMAGE_ORIENTATION_VERTICAL",
            ),
            "color": _coerce_enum(
                cfg.get("yandex_official_color"),
                _IMAGE_SPEC["color"], "IMAGE_COLOR_COLOR",
            ),
        },
        "docs_on_page": "20",
        "folder_id": _get_creds()[1],
        "user_agent": _USER_AGENT,
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
    last_exc = None
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
            # Surface the server-side error body so users can
            # diagnose missing scope / wrong folder id / disabled
            # API without grepping the Anki console.
            last_exc = exc
            body_text = ""
            status = getattr(getattr(exc, "response", None), "status_code", None)
            try:
                resp = getattr(exc, "response", None)
                if resp is not None:
                    body_text = (resp.text or "")[:500]
            except Exception:
                pass
            log.warning(
                "yandex_official: giving up query=%r err=%r status=%s body=%r",
                query, exc, status, body_text,
            )
            if status in (400, 401, 403, 404):
                # Auth/config error - no point retrying.
                return []
            if attempt < max_retries:
                time.sleep(backoff_base_s * (2 ** attempt))
                continue
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
