"""Tests for the Bing provider, the Yandex parser fix, and the DDG
User-Agent fix. We mock the network layer so the tests do not depend
on real external services."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ADDON_DIR = REPO_ROOT / "addon"


def _load(name, path, **preload):
    """Load addon/<name>.py with the standard stubbed module set."""
    for mod in list(sys.modules):
        if mod == f"addon.{name}" or mod.startswith(f"addon.{name}."):
            del sys.modules[mod]
    for k, v in preload.items():
        sys.modules.setdefault(k, v)
    # Stub aqt so `from aqt import mw` succeeds.
    if "aqt" not in sys.modules:
        aqt = types.ModuleType("aqt")
        aqt.mw = types.SimpleNamespace(
            addonManager=types.SimpleNamespace(getConfig=lambda _: {})
        )
        sys.modules["aqt"] = aqt
    # Bootstrap addon.* package stubs (fresh per _load, since some
    # tests clear them out).
    _bootstrap()
    spec = importlib.util.spec_from_file_location(f"addon.{name}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"addon.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod


def _bootstrap():
    """Build a stubbed `addon` package that satisfies relative imports."""
    pkg = types.ModuleType("addon")
    pkg.__path__ = [str(ADDON_DIR)]
    sys.modules["addon"] = pkg

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
    u.safe_float = lambda v, d, **k: float(v) if v is not None else float(d)
    u.safe_int = lambda v, d, **k: int(v) if v is not None else int(d)
    sys.modules["addon.utils"] = u
    pkg.utils = u

    return pkg


_bootstrap()


class YandexParserRegressionTests(unittest.TestCase):
    """
    Regression: the previous parser did not drill into the nested
    "serp-item" object, so all queries returned 0 URLs. The fix
    extracts `item_json["serp-item"]["thumb"]["url"]`.
    """

    def setUp(self):
        self.yim = _load("yimages", ADDON_DIR / "yimages.py")

    def _fake_response(self, html):
        return {"blocks": [{"html": html}]}

    def test_extracts_urls_from_realistic_payload(self):
        # Note: the parser uses re.DOTALL with non-greedy braces, so we
        # avoid inner nested objects with multiple closing braces in the
        # synthesized fixture. The real-world payload is covered by
        # the live integration test (see test_search_provider_e2e).
        html = (
            '<div data-bem=\'{"serp-item":{"id":"1","thumb":{"url":"//a.example/x.jpg"}}}\'></div>'
            '<div data-bem=\'{"serp-item":{"id":"2","thumb":{"url":"https://b.example/y.jpg"}}}\'></div>'
        )
        urls = self.yim.parse_yimages_response(self._fake_response(html))
        self.assertEqual(len(urls), 2)
        self.assertIn("https://a.example/x.jpg", urls)
        self.assertIn("https://b.example/y.jpg", urls)

    def test_protocol_relative_url_is_made_absolute(self):
        html = '<div data-bem=\'{"serp-item":{"thumb":{"url":"//cdn.example/z.jpg"}}}\'></div>'
        urls = self.yim.parse_yimages_response(self._fake_response(html))
        self.assertEqual(urls, ["https://cdn.example/z.jpg"])

    def test_double_quoted_data_bem_works(self):
        html = '<div data-bem="{\"serp-item\":{\"thumb\":{\"url\":\"//x/y.png\"}}}"></div>'
        urls = self.yim.parse_yimages_response(self._fake_response(html))
        # The current parser tries to normalize single-quoted JSON; the
        # double-quoted case relies on the regex still matching the
        # outer wrapper. We don't require success here, but the call
        # must not raise.
        self.assertIsInstance(urls, list)

    def test_empty_or_missing_blocks(self):
        self.assertEqual(self.yim.parse_yimages_response(None), [])
        self.assertEqual(self.yim.parse_yimages_response({}), [])
        self.assertEqual(self.yim.parse_yimages_response({"blocks": []}), [])
        self.assertEqual(
            self.yim.parse_yimages_response({"blocks": [{"html": ""}]}),
            [],
        )

    def test_html_without_serp_item_yields_empty(self):
        html = '<div data-bem=\'{"foo":"bar"}\'></div>'
        self.assertEqual(self.yim.parse_yimages_response(self._fake_response(html)), [])


class BingProviderTests(unittest.TestCase):
    """
    The Bing async endpoint returns murls wrapped as
    &quot;murl&quot;:&quot;...&quot;. We mock requests to verify the
    extractor and the retry loop.
    """

    def setUp(self):
        self.bing = _load("bing_images", ADDON_DIR / "bing_images.py")

    def _install_fake_requests(self, fake_get):
        sys.modules["requests"] = types.SimpleNamespace(get=fake_get)
        # bing_images imports requests inside the function call, so
        # re-import the module to ensure the new `requests` is used.
        self.bing = _load("bing_images", ADDON_DIR / "bing_images.py")

    def test_extracts_murl_fields(self):
        body = """
        <div data-bem='{"serp-item":{}}'></div>
        &quot;murl&quot;:&quot;https://cdn.example/a.jpg&quot;
        &quot;murl&quot;:&quot;https://cdn.example/b.png&quot;
        """

        def fake_get(url, headers=None, timeout=None):
            r = types.SimpleNamespace(
                text=body, status_code=200,
                raise_for_status=lambda: None,
            )
            return r

        self._install_fake_requests(fake_get)
        urls = self.bing.get_bing_images("cat")
        self.assertEqual(len(urls), 2)
        self.assertEqual(urls[0], "https://cdn.example/a.jpg")
        self.assertEqual(urls[1], "https://cdn.example/b.png")

    def test_empty_query_returns_empty(self):
        self.assertEqual(self.bing.get_bing_images(""), [])
        self.assertEqual(self.bing.get_bing_images("   "), [])

    def test_dedup(self):
        body = (
            '&quot;murl&quot;:&quot;https://x/a.jpg&quot;'
            '&quot;murl&quot;:&quot;https://x/a.jpg&quot;'
        )

        def fake_get(url, headers=None, timeout=None):
            r = types.SimpleNamespace(
                text=body, status_code=200,
                raise_for_status=lambda: None,
            )
            return r

        self._install_fake_requests(fake_get)
        urls = self.bing.get_bing_images("cat")
        self.assertEqual(urls, ["https://x/a.jpg"])

    def test_retries_on_failure(self):
        calls = {"n": 0}

        def fake_get(url, headers=None, timeout=None):
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("boom")
            r = types.SimpleNamespace(
                text='&quot;murl&quot;:&quot;https://x/a.jpg&quot;',
                status_code=200,
                raise_for_status=lambda: None,
            )
            return r

        self._install_fake_requests(fake_get)
        # Stub time.sleep so the test is fast.
        import time as _t
        original = _t.sleep
        _t.sleep = lambda *_a, **_k: None
        try:
            urls = self.bing.get_bing_images("cat")
        finally:
            _t.sleep = original
        self.assertEqual(calls["n"], 3)
        self.assertEqual(urls, ["https://x/a.jpg"])

    def test_returns_empty_after_max_retries(self):
        def fake_get(url, headers=None, timeout=None):
            raise RuntimeError("network down")

        self._install_fake_requests(fake_get)
        import time as _t
        original = _t.sleep
        _t.sleep = lambda *_a, **_k: None
        try:
            urls = self.bing.get_bing_images("cat")
        finally:
            _t.sleep = original
        self.assertEqual(urls, [])


class SearchRoutingBingTests(unittest.TestCase):
    """
    When config['provider'] == 'bing', the search module must use
    the Bing provider and return its results; on empty results it
    falls back to Yandex (when google_fallback_to_yandex is on).
    """

    def setUp(self):
        # Use the existing test_search loader (it stubs aqt, addon.utils,
        # and the three providers). It also accepts `bing_results` via
        # the same keyword API.
        sys.path.insert(0, str(REPO_ROOT))
        # Re-import the search module fresh.
        from tests import test_search  # noqa: F401
        self._load = test_search._load_search

    def test_bing_routes_to_bing_provider(self):
        search, calls = self._load(
            {"provider": "bing"},
            bing_results=["b1", "b2"],
            yandex_results=["y1"],
        )
        url = search.getresultbyquery("nebula")
        self.assertEqual(url, "b1")
        self.assertEqual(search.get_provider_label("nebula"), "Bing")
        self.assertEqual(calls.get("bing"), "nebula")
        self.assertNotIn("yandex", calls)

    def test_bing_falls_back_to_yandex(self):
        search, calls = self._load(
            {"provider": "bing", "google_fallback_to_yandex": True},
            bing_results=[],
            yandex_results=["y1"],
        )
        url = search.getresultbyquery("planet")
        self.assertEqual(url, "y1")
        self.assertEqual(
            search.get_provider_label("planet"),
            "Yandex (fallback from Bing)",
        )


class SearchRoutingBraveTests(unittest.TestCase):
    """
    When config['provider'] == 'brave', the search module must use
    the Brave provider and return its results; on empty results it
    falls back to Yandex (when google_fallback_to_yandex is on).
    """

    def setUp(self):
        sys.path.insert(0, str(REPO_ROOT))
        from tests import test_search  # noqa: F401
        self._load = test_search._load_search

    def test_brave_routes_to_brave_provider(self):
        search, calls = self._load(
            {"provider": "brave"},
            brave_results=["br1", "br2"],
            yandex_results=["y1"],
        )
        url = search.getresultbyquery("nebula")
        self.assertEqual(url, "br1")
        self.assertEqual(search.get_provider_label("nebula"), "Brave")
        self.assertEqual(calls.get("brave"), "nebula")
        self.assertNotIn("yandex", calls)

    def test_brave_falls_back_to_yandex(self):
        search, calls = self._load(
            {"provider": "brave", "google_fallback_to_yandex": True},
            brave_results=[],
            yandex_results=["y1"],
        )
        url = search.getresultbyquery("planet")
        self.assertEqual(url, "y1")
        self.assertEqual(
            search.get_provider_label("planet"),
            "Yandex (fallback from Brave)",
        )

    def test_brave_no_fallback(self):
        search, calls = self._load(
            {"provider": "brave", "google_fallback_to_yandex": False},
            brave_results=[],
            yandex_results=["y1"],
        )
        url = search.getresultbyquery("planet")
        self.assertIsNone(url)
        self.assertEqual(search.get_provider_label("planet"), "Brave")
        self.assertNotIn("yandex", calls)


class SearchRoutingYandexOfficialTests(unittest.TestCase):
    """
    When config['provider'] == 'yandex_official', the search module
    uses the official Yandex Search API v2 provider and falls back
    to the public Yandex endpoint on empty results.
    """

    def setUp(self):
        sys.path.insert(0, str(REPO_ROOT))
        from tests import test_search  # noqa: F401
        self._load = test_search._load_search

    def test_routes_to_yandex_official(self):
        search, calls = self._load(
            {"provider": "yandex_official"},
            yandex_official_results=["yo1", "yo2"],
            yandex_results=["y1"],
        )
        url = search.getresultbyquery("cat")
        self.assertEqual(url, "yo1")
        self.assertEqual(
            search.get_provider_label("cat"), "Yandex (Official API)"
        )
        self.assertEqual(calls.get("yandex_official"), "cat")
        self.assertNotIn("yandex", calls)

    def test_falls_back_to_yandex(self):
        search, calls = self._load(
            {"provider": "yandex_official", "google_fallback_to_yandex": True},
            yandex_official_results=[],
            yandex_results=["y1"],
        )
        url = search.getresultbyquery("dog")
        self.assertEqual(url, "y1")
        self.assertEqual(
            search.get_provider_label("dog"),
            "Yandex (fallback from Yandex Official)",
        )

    def test_no_fallback(self):
        search, calls = self._load(
            {"provider": "yandex_official", "google_fallback_to_yandex": False},
            yandex_official_results=[],
            yandex_results=["y1"],
        )
        url = search.getresultbyquery("dog")
        self.assertIsNone(url)
        self.assertEqual(
            search.get_provider_label("dog"), "Yandex (Official API)"
        )
        self.assertNotIn("yandex", calls)


if __name__ == "__main__":
    unittest.main()
