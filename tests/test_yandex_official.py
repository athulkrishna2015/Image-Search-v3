"""Tests for the official Yandex Search API v2 provider."""
import base64
import importlib.util
import sys
import types
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ADDON_DIR = REPO_ROOT / "addon"


def _bootstrap():
    pkg = types.ModuleType("addon")
    pkg.__path__ = [str(ADDON_DIR)]
    sys.modules["addon"] = pkg

    aqt = types.ModuleType("aqt")

    def _get_config(_name):
        return _CONFIG.get("aqt_config", {})
    aqt.mw = types.SimpleNamespace(
        addonManager=types.SimpleNamespace(getConfig=_get_config)
    )
    sys.modules["aqt"] = aqt

    log = types.ModuleType("addon.logger")
    log.log = types.SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        error=lambda *a, **k: None,
        debug=lambda *a, **k: None,
    )
    sys.modules["addon.logger"] = log
    pkg.logger = log

    u = types.ModuleType("addon.utils")
    u.get_net_settings = lambda: (10.0, 5, 0.75)
    sys.modules["addon.utils"] = u
    pkg.utils = u


_CONFIG: dict = {}
_bootstrap()


def _load(extra_aqt_config=None):
    if extra_aqt_config is not None:
        _CONFIG["aqt_config"] = extra_aqt_config
    if "addon.yandex_official" in sys.modules:
        del sys.modules["addon.yandex_official"]
    # Patch the addonManager.getConfig closure on the shared aqt
    # module so the reloaded yandex_official sees the new config.
    aqt = sys.modules["aqt"]
    def _get_config(_name):
        return _CONFIG.get("aqt_config", {})
    aqt.mw.addonManager = types.SimpleNamespace(getConfig=_get_config)
    spec = importlib.util.spec_from_file_location(
        "addon.yandex_official", ADDON_DIR / "yandex_official.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.yandex_official"] = mod
    spec.loader.exec_module(mod)
    return mod


def _build_xml(doc_urls):
    """
    Build a minimal Yandex XML response with the given original
    image URLs. The path inside <group> follows the documented
    Yandex schema:
        .../doc/properties/img/image-doc/image-shown/url
    The `&` in URLs is properly XML-escaped as `&amp;`, matching
    the format the official API actually returns.
    """
    docs_xml = ""
    for i, url in enumerate(doc_urls):
        docs_xml += f"""
    <group id="g{i}">
      <doc id="d{i}">
        <url>https://example.com/page{i}</url>
        <title>Image {i}</title>
        <properties>
          <img>
            <image-doc>
              <image-shown>
                <url>{url}</url>
                <width>800</width>
                <height>600</height>
              </image-shown>
              <thumbnails>
                <thumbnail url="https://cdn.example.com/thumb{i}.jpg" width="200" height="150"/>
              </thumbnails>
            </image-doc>
          </img>
        </properties>
      </doc>
    </group>"""
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<yandexsearch version="1.0">
  <response>
    <results>
      <grouping attr="d" mode="flat" groups-on-page="{len(doc_urls)}" docs-in-group="1">{docs_xml}
      </grouping>
    </results>
  </response>
</yandexsearch>"""
    return xml


class ParseYandexOfficialTests(unittest.TestCase):
    def setUp(self):
        self.mod = _load(extra_aqt_config={})

    def test_returns_empty_for_empty_input(self):
        self.assertEqual(self.mod.parse_yandex_official_response(""), [])
        self.assertEqual(self.mod.parse_yandex_official_response(None), [])
        self.assertEqual(self.mod.parse_yandex_official_response("not b64!"), [])

    def test_decodes_base64_and_extracts_urls(self):
        xml = _build_xml([
            "https://avatars.mds.yandex.net/i?id=1&amp;n=1",
            "https://avatars.mds.yandex.net/i?id=2&amp;n=1",
        ])
        b64 = base64.b64encode(xml.encode("utf-8")).decode("ascii")
        urls = self.mod.parse_yandex_official_response(b64)
        self.assertEqual(
            urls,
            [
                "https://avatars.mds.yandex.net/i?id=1&n=1",
                "https://avatars.mds.yandex.net/i?id=2&n=1",
            ],
        )

    def test_protocol_relative_url_becomes_https(self):
        xml = _build_xml(["//avatars.mds.yandex.net/i?id=3&amp;n=1"])
        b64 = base64.b64encode(xml.encode("utf-8")).decode("ascii")
        urls = self.mod.parse_yandex_official_response(b64)
        self.assertEqual(
            urls, ["https://avatars.mds.yandex.net/i?id=3&n=1"],
        )

    def test_dedup(self):
        xml = _build_xml([
            "https://avatars.mds.yandex.net/i?id=1",
            "https://avatars.mds.yandex.net/i?id=1",
            "https://avatars.mds.yandex.net/i?id=2",
        ])
        b64 = base64.b64encode(xml.encode("utf-8")).decode("ascii")
        urls = self.mod.parse_yandex_official_response(b64)
        self.assertEqual(
            urls,
            [
                "https://avatars.mds.yandex.net/i?id=1",
                "https://avatars.mds.yandex.net/i?id=2",
            ],
        )

    def test_skips_doc_without_image_doc(self):
        xml = """<?xml version="1.0"?>
<yandexsearch version="1.0">
  <response>
    <results>
      <grouping>
        <group id="g">
          <doc>
            <url>https://example.com/noimg</url>
            <title>No image here</title>
            <properties></properties>
          </doc>
        </group>
        <group id="g2">
          <doc>
            <url>https://example.com/yes</url>
            <properties>
              <img>
                <image-doc>
                  <image-shown>
                    <url>https://avatars.mds.yandex.net/i?id=ok</url>
                  </image-shown>
                </image-doc>
              </img>
            </properties>
          </doc>
        </group>
      </grouping>
    </results>
  </response>
</yandexsearch>"""
        b64 = base64.b64encode(xml.encode("utf-8")).decode("ascii")
        urls = self.mod.parse_yandex_official_response(b64)
        self.assertEqual(urls, ["https://avatars.mds.yandex.net/i?id=ok"])

    def test_skips_image_doc_without_url_text(self):
        xml = """<?xml version="1.0"?>
<yandexsearch version="1.0">
  <response>
    <results>
      <grouping>
        <group id="g">
          <doc>
            <properties>
              <img>
                <image-doc>
                  <image-shown>
                    <url></url>
                  </image-shown>
                </image-doc>
              </img>
            </properties>
          </doc>
        </group>
      </grouping>
    </results>
  </response>
</yandexsearch>"""
        b64 = base64.b64encode(xml.encode("utf-8")).decode("ascii")
        urls = self.mod.parse_yandex_official_response(b64)
        self.assertEqual(urls, [])


class GetYandexOfficialImagesTests(unittest.TestCase):
    def setUp(self):
        self.mod = _load(extra_aqt_config={})

    def test_missing_creds_returns_empty(self):
        self.assertEqual(self.mod.get_yandex_official_images("cat"), [])
        self.mod = _load(extra_aqt_config={"yandex_api_key": "k"})
        self.assertEqual(self.mod.get_yandex_official_images("cat"), [])
        self.mod = _load(extra_aqt_config={"yandex_folder_id": "f"})
        self.assertEqual(self.mod.get_yandex_official_images("cat"), [])

    def test_empty_query_returns_empty(self):
        self.mod = _load(extra_aqt_config={"yandex_api_key": "k", "yandex_folder_id": "f"})
        self.assertEqual(self.mod.get_yandex_official_images(""), [])
        self.assertEqual(self.mod.get_yandex_official_images("   "), [])

    def test_sends_correct_request(self):
        captured = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            captured["timeout"] = timeout
            xml = _build_xml(["https://avatars.mds.yandex.net/i?id=x"])
            return types.SimpleNamespace(
                status_code=200,
                content=b"{}",
                raise_for_status=lambda: None,
                json=lambda: {
                    "rawData": base64.b64encode(xml.encode("utf-8")).decode("ascii")
                },
            )

        exc_mod = types.ModuleType("requests.exceptions")
        exc_mod.Timeout = type("Timeout", (Exception,), {})
        exc_mod.HTTPError = type("HTTPError", (Exception,), {})
        fake_requests = types.ModuleType("requests")
        fake_requests.post = fake_post
        fake_requests.exceptions = exc_mod
        # Install the fake BEFORE the module is reloaded so the
        # `import requests` inside the function picks it up.
        real_requests = sys.modules.pop("requests", None)
        sys.modules["requests"] = fake_requests
        sys.modules["requests.exceptions"] = exc_mod
        try:
            self.mod = _load(
                extra_aqt_config={
                    "yandex_api_key": "yakey",
                    "yandex_folder_id": "b1g_folder",
                }
            )
            urls = self.mod.get_yandex_official_images("cat")
        finally:
            sys.modules.pop("requests", None)
            sys.modules.pop("requests.exceptions", None)
            if real_requests is not None:
                sys.modules["requests"] = real_requests

        self.assertEqual(urls, ["https://avatars.mds.yandex.net/i?id=x"])
        self.assertEqual(
            captured["url"],
            "https://searchapi.api.cloud.yandex.net/v2/image/search",
        )
        self.assertEqual(
            captured["headers"]["Authorization"], "Api-Key yakey"
        )
        self.assertEqual(captured["headers"]["Content-Type"], "application/json")
        self.assertEqual(captured["json"]["query"]["queryText"], "cat")
        self.assertEqual(captured["json"]["query"]["searchType"], "com")
        self.assertEqual(captured["json"]["query"]["familyMode"], "moderate")
        self.assertEqual(captured["json"]["folderId"], "b1g_folder")
        self.assertEqual(captured["json"]["docsOnPage"], "20")

    def test_retries_on_timeout(self):
        calls = {"n": 0}

        def fake_post(url, headers=None, json=None, timeout=None):
            calls["n"] += 1
            if calls["n"] < 3:
                raise exc_mod.Timeout("slow")
            xml = _build_xml(["https://avatars.mds.yandex.net/i?id=z"])
            return types.SimpleNamespace(
                status_code=200,
                content=b"{}",
                raise_for_status=lambda: None,
                json=lambda: {
                    "rawData": base64.b64encode(xml.encode("utf-8")).decode("ascii")
                },
            )

        exc_mod = types.ModuleType("requests.exceptions")
        exc_mod.Timeout = type("Timeout", (Exception,), {})
        exc_mod.HTTPError = type("HTTPError", (Exception,), {})
        fake_requests = types.ModuleType("requests")
        fake_requests.post = fake_post
        fake_requests.exceptions = exc_mod
        real_requests = sys.modules.pop("requests", None)
        sys.modules["requests"] = fake_requests
        sys.modules["requests.exceptions"] = exc_mod
        import time as _t
        original_sleep = _t.sleep
        _t.sleep = lambda *_a, **_k: None
        try:
            self.mod = _load(
                extra_aqt_config={
                    "yandex_api_key": "k",
                    "yandex_folder_id": "f",
                }
            )
            urls = self.mod.get_yandex_official_images("cat")
        finally:
            _t.sleep = original_sleep
            sys.modules.pop("requests", None)
            sys.modules.pop("requests.exceptions", None)
            if real_requests is not None:
                sys.modules["requests"] = real_requests
        self.assertEqual(calls["n"], 3)
        self.assertEqual(urls, ["https://avatars.mds.yandex.net/i?id=z"])

    def test_returns_empty_on_4xx(self):
        def fake_post(url, headers=None, json=None, timeout=None):
            def raise_():
                raise exc_mod.HTTPError("401")
            return types.SimpleNamespace(
                status_code=401, content=b"", raise_for_status=raise_
            )

        exc_mod = types.ModuleType("requests.exceptions")
        exc_mod.Timeout = type("Timeout", (Exception,), {})
        exc_mod.HTTPError = type("HTTPError", (Exception,), {})
        fake_requests = types.ModuleType("requests")
        fake_requests.post = fake_post
        fake_requests.exceptions = exc_mod
        real_requests = sys.modules.pop("requests", None)
        sys.modules["requests"] = fake_requests
        sys.modules["requests.exceptions"] = exc_mod
        try:
            self.mod = _load(
                extra_aqt_config={"yandex_api_key": "k", "yandex_folder_id": "f"}
            )
            urls = self.mod.get_yandex_official_images("cat")
        finally:
            sys.modules.pop("requests", None)
            sys.modules.pop("requests.exceptions", None)
            if real_requests is not None:
                sys.modules["requests"] = real_requests
        self.assertEqual(urls, [])


if __name__ == "__main__":
    unittest.main()
