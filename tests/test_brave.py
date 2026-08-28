"""Tests for the Brave Image Search API provider."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ADDON_DIR = REPO_ROOT / "addon"


def _bootstrap():
    """Build a stubbed `addon` package that satisfies relative imports."""
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


def _load_brave(extra_aqt_config=None):
    """Load addon/brave_images.py with the standard stubs."""
    if "aqt_config" not in _CONFIG and extra_aqt_config is not None:
        _CONFIG["aqt_config"] = extra_aqt_config
    elif extra_aqt_config is not None:
        _CONFIG["aqt_config"] = extra_aqt_config
    for name in list(sys.modules):
        if name == "addon.brave_images":
            del sys.modules[name]
    # Patch the addonManager.getConfig closure by mutating the existing
    # aqt module so the new brave_images sees the same aqt.
    aqt = sys.modules["aqt"]
    def _get_config(_name):
        return _CONFIG.get("aqt_config", {})
    aqt.mw.addonManager = types.SimpleNamespace(getConfig=_get_config)
    spec = importlib.util.spec_from_file_location(
        "addon.brave_images", ADDON_DIR / "brave_images.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.brave_images"] = mod
    spec.loader.exec_module(mod)
    return mod


class BraveParserTests(unittest.TestCase):
    """
    The Brave Image Search response shape (per the docs):

    {
      "type": "images",
      "query": {...},
      "results": [
        {
          "type": "image_result",
          "title": "...",
          "url": "https://example.com/page",  // page URL, NOT the image
          "thumbnail": {"src": "https://imgs.search.brave.com/.../thumb.jpg", ...},
          "properties": {
            "url": "https://example.com/images/full.jpg",  // original image URL
            "placeholder": "https://imgs.search.brave.com/.../placeholder",
            "width": 1920,
            "height": 1080
          }
        }
      ],
      "extra": {...}
    }
    """

    def setUp(self):
        self.brave = _load_brave()

    def test_extracts_original_url_from_properties(self):
        response = {
            "type": "images",
            "results": [
                {
                    "type": "image_result",
                    "title": "A cat",
                    "url": "https://example.com/cats/page",
                    "thumbnail": {"src": "https://imgs.search.brave.com/cat-thumb.jpg"},
                    "properties": {"url": "https://example.com/images/cat.jpg"},
                }
            ],
        }
        urls = self.brave.parse_brave_response(response)
        self.assertEqual(urls, ["https://example.com/images/cat.jpg"])

    def test_falls_back_to_thumbnail_when_properties_missing(self):
        response = {
            "results": [
                {
                    "type": "image_result",
                    "url": "https://example.com/cats/page",
                    "thumbnail": {"src": "https://imgs.search.brave.com/cat-thumb.jpg"},
                }
            ]
        }
        urls = self.brave.parse_brave_response(response)
        self.assertEqual(urls, ["https://imgs.search.brave.com/cat-thumb.jpg"])

    def test_does_not_use_page_url_as_image(self):
        """
        The `url` field is the PAGE URL, not the image URL. We must
        not fall back to it.
        """
        response = {
            "results": [
                {
                    "type": "image_result",
                    "url": "https://example.com/cats/page",
                }
            ]
        }
        urls = self.brave.parse_brave_response(response)
        self.assertEqual(urls, [])

    def test_dedup(self):
        response = {
            "results": [
                {"properties": {"url": "https://x/a.jpg"}},
                {"properties": {"url": "https://x/a.jpg"}},
                {"properties": {"url": "https://x/b.jpg"}},
            ]
        }
        urls = self.brave.parse_brave_response(response)
        self.assertEqual(urls, ["https://x/a.jpg", "https://x/b.jpg"])

    def test_empty_or_invalid(self):
        self.assertEqual(self.brave.parse_brave_response(None), [])
        self.assertEqual(self.brave.parse_brave_response({}), [])
        self.assertEqual(self.brave.parse_brave_response({"results": "bad"}), [])
        self.assertEqual(self.brave.parse_brave_response({"results": []}), [])

    def test_skips_non_dict_results(self):
        response = {
            "results": [
                "not a dict",
                {"properties": {"url": "https://x/ok.jpg"}},
                None,
                {"properties": None},
            ]
        }
        urls = self.brave.parse_brave_response(response)
        self.assertEqual(urls, ["https://x/ok.jpg"])


class BraveProviderRequestTests(unittest.TestCase):
    """
    Mock the requests.get call and verify that the Brave provider
    - sends the correct headers (X-Subscription-Token)
    - sends the correct query parameters (q, count, safesearch)
    - returns [] on any error / missing key
    - retries with backoff on timeout
    """

    @classmethod
    def setUpClass(cls):
        cls.exc_mod = types.ModuleType("requests.exceptions")
        cls.exc_mod.Timeout = type("Timeout", (Exception,), {})
        cls.exc_mod.RequestException = type("RequestException", (Exception,), {})
        cls.exc_mod.HTTPError = type("HTTPError", (Exception,), {})
        sys.modules["requests.exceptions"] = cls.exc_mod

    def setUp(self):
        self.brave = _load_brave(extra_aqt_config={"brave_api_key": "BSAkey"})

    def _install_fake_requests(self, fake_get):
        """Install a fake `requests` module with proper exceptions namespace."""
        fake_requests = types.ModuleType("requests")
        fake_requests.get = fake_get
        fake_requests.exceptions = self.exc_mod
        sys.modules["requests"] = fake_requests
        self.brave = _load_brave(extra_aqt_config={"brave_api_key": "BSAkey"})

    def test_missing_key_returns_empty(self):
        self.brave = _load_brave(extra_aqt_config={})
        self.assertEqual(self.brave.get_brave_images("cat"), [])

    def test_empty_query_returns_empty(self):
        self.assertEqual(self.brave.get_brave_images(""), [])

    def test_sends_subscription_token(self):
        captured = {}

        def fake_get(url, params=None, headers=None, timeout=None):
            captured["url"] = url
            captured["params"] = params
            captured["headers"] = headers
            captured["timeout"] = timeout
            return types.SimpleNamespace(
                status_code=200,
                content=b"{}",
                json=lambda: {"results": [
                    {"properties": {"url": "https://x/a.jpg"}}
                ]},
                raise_for_status=lambda: None,
            )

        self._install_fake_requests(fake_get)
        urls = self.brave.get_brave_images("cat")
        self.assertEqual(urls, ["https://x/a.jpg"])
        self.assertEqual(captured["headers"]["X-Subscription-Token"], "BSAkey")
        self.assertEqual(captured["headers"]["Accept"], "application/json")
        self.assertEqual(captured["params"]["q"], "cat")
        self.assertEqual(captured["params"]["count"], 50)
        self.assertEqual(captured["params"]["safesearch"], "strict")
        self.assertIn("res/v1/images/search", captured["url"])

    def test_returns_empty_on_4xx(self):
        def fake_get(url, params=None, headers=None, timeout=None):
            def raise_():
                raise self.exc_mod.HTTPError("401")
            return types.SimpleNamespace(
                status_code=401, content=b"", raise_for_status=raise_
            )

        self._install_fake_requests(fake_get)
        self.assertEqual(self.brave.get_brave_images("cat"), [])

    def test_retries_on_timeout(self):
        calls = {"n": 0}

        def fake_get(url, params=None, headers=None, timeout=None):
            calls["n"] += 1
            if calls["n"] < 3:
                raise self.exc_mod.Timeout("slow")
            return types.SimpleNamespace(
                status_code=200,
                content=b"{}",
                json=lambda: {"results": [
                    {"properties": {"url": "https://x/a.jpg"}}
                ]},
                raise_for_status=lambda: None,
            )

        import time as _t
        original = _t.sleep
        _t.sleep = lambda *_a, **_k: None
        try:
            self._install_fake_requests(fake_get)
            urls = self.brave.get_brave_images("cat")
        finally:
            _t.sleep = original
        self.assertEqual(calls["n"], 3)
        self.assertEqual(urls, ["https://x/a.jpg"])

    def test_returns_empty_after_max_retries(self):
        def fake_get(url, params=None, headers=None, timeout=None):
            raise self.exc_mod.Timeout("dead")

        import time as _t
        original = _t.sleep
        _t.sleep = lambda *_a, **_k: None
        try:
            self._install_fake_requests(fake_get)
            urls = self.brave.get_brave_images("cat")
        finally:
            _t.sleep = original
        self.assertEqual(urls, [])


if __name__ == "__main__":
    unittest.main()
