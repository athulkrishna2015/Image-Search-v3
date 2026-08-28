import importlib.util
import sys
import types
import unittest
from pathlib import Path


def _make_module(name, **attrs):
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    return mod


def _load_search(config, ddg_results=None, yandex_results=None, google_results=None, bing_results=None, brave_results=None, yandex_official_results=None, strip_fn=None):
    # Clear prior stubs/modules
    for name in [
        "addon.search",
        "addon.utils",
        "addon.yimages",
        "addon.gimages",
        "addon.ddg_hidden_test",
        "addon.bing_images",
        "addon.brave_images",
        "addon.yandex_official",
        "addon.logger",
        "addon",
        "anki",
        "anki.utils",
    ]:
        sys.modules.pop(name, None)

    # Stub anki.utils.strip_html_media
    if strip_fn is None:
        strip_fn = lambda s: s
    anki_utils = _make_module("anki.utils", strip_html_media=strip_fn)
    anki = _make_module("anki", utils=anki_utils)
    sys.modules["anki"] = anki
    sys.modules["anki.utils"] = anki_utils

    # Stub addon package
    repo_root = Path(__file__).resolve().parents[1]
    addon_pkg = types.ModuleType("addon")
    addon_pkg.__path__ = [str(repo_root / "addon")]
    sys.modules["addon"] = addon_pkg

    # Stub addon.utils.get_config
    addon_utils = _make_module("addon.utils", get_config=lambda: config)
    sys.modules["addon.utils"] = addon_utils

    # Search tests use fixture queries and must never write them to the
    # add-on's real runtime log in addon/logs/.
    noop_log = types.SimpleNamespace(
        debug=lambda *a, **k: None,
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        error=lambda *a, **k: None,
    )
    sys.modules["addon.logger"] = _make_module("addon.logger", log=noop_log)

    # Provider stubs with call capture
    calls = {}

    def _ddg(q):
        calls["ddg"] = q
        return list(ddg_results or [])

    def _yandex(q):
        calls["yandex"] = q
        return list(yandex_results or [])

    def _google(q):
        calls["google"] = q
        return list(google_results or [])

    def _bing(q):
        calls["bing"] = q
        return list(bing_results or [])

    def _brave(q):
        calls["brave"] = q
        return list(brave_results or [])

    def _yandex_official(q):
        calls["yandex_official"] = q
        return list(yandex_official_results or [])

    sys.modules["addon.ddg_hidden_test"] = _make_module(
        "addon.ddg_hidden_test", get_ddg_images=_ddg, getddgimages=_ddg
    )
    sys.modules["addon.yimages"] = _make_module(
        "addon.yimages", get_yimages=_yandex, getyimages=_yandex
    )
    sys.modules["addon.gimages"] = _make_module("addon.gimages", getgimages=_google)
    sys.modules["addon.bing_images"] = _make_module(
        "addon.bing_images", get_bing_images=_bing
    )
    sys.modules["addon.brave_images"] = _make_module(
        "addon.brave_images", get_brave_images=_brave
    )
    sys.modules["addon.yandex_official"] = _make_module(
        "addon.yandex_official",
        get_yandex_official_images=_yandex_official,
        getyandexofficial=_yandex_official,
    )

    # Load addon.search without executing addon/__init__.py
    search_path = repo_root / "addon" / "search.py"
    spec = importlib.util.spec_from_file_location("addon.search", search_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["addon.search"] = module
    spec.loader.exec_module(module)
    # Clear any cached provider resolvers from a previous test in the
    # same process. _load_search is called per-test; the search module
    # is reloaded via exec_module but module-level state (notably
    # _RESOLVER_CACHE) persists on the same module object across
    # re-runs when sys.modules reuses the entry.
    if hasattr(module, "_RESOLVER_CACHE"):
        module._RESOLVER_CACHE.clear()
    return module, calls


class SearchProviderTests(unittest.TestCase):
    def test_ddg_fallback_to_yandex_label(self):
        config = {"provider": "duckduckgo"}
        search, calls = _load_search(config, ddg_results=[], yandex_results=["y1"])
        url = search.getresultbyquery("cats")
        self.assertEqual(url, "y1")
        self.assertEqual(
            search.get_provider_label("cats"),
            "Yandex (unofficial) (fallback for DuckDuckGo (unofficial))",
        )
        self.assertEqual(calls.get("ddg"), "cats")
        self.assertEqual(calls.get("yandex"), "cats")

    def test_ddg_primary_label(self):
        config = {"provider": "ddg"}
        search, calls = _load_search(config, ddg_results=["d1", "d2"], yandex_results=["y1"])
        url = search.getresultbyquery("nebula")
        self.assertEqual(url, "d1")
        self.assertEqual(
            search.get_provider_label("nebula"), "DuckDuckGo (unofficial)"
        )
        self.assertEqual(calls.get("ddg"), "nebula")
        self.assertNotIn("yandex", calls)

    def test_google_fallback_label(self):
        config = {"provider": "google"}
        search, calls = _load_search(config, google_results=[], yandex_results=["y1"])
        url = search.getresultbyquery("planet")
        self.assertEqual(url, "y1")
        self.assertEqual(
            search.get_provider_label("planet"),
            "Yandex (unofficial) (fallback for Google)",
        )
        self.assertEqual(calls.get("google"), "planet")
        self.assertEqual(calls.get("yandex"), "planet")

    def test_google_no_fallback_label(self):
        # When the chain is empty, we still call the primary and
        # return its label even on no results.
        config = {"provider": "google", "fallback_google": []}
        search, calls = _load_search(config, google_results=[], yandex_results=["y1"])
        url = search.getresultbyquery("planet")
        self.assertIsNone(url)
        self.assertEqual(search.get_provider_label("planet"), "Google")
        self.assertEqual(calls.get("google"), "planet")
        self.assertNotIn("yandex", calls)

    def test_google_legacy_fallback_flag_still_works(self):
        # Old configs use `google_fallback_to_yandex`. New chains
        # override it. Verify backwards compat: an old config without
        # `fallback_google` still falls back to Yandex (since
        # DEFAULT_FALLBACKS['google'] = ('yandex', 'bing', 'duckduckgo')).
        config = {"provider": "google", "google_fallback_to_yandex": True}
        search, calls = _load_search(config, google_results=[], yandex_results=["y1"])
        url = search.getresultbyquery("planet")
        self.assertEqual(url, "y1")
        self.assertIn("google", calls)
        self.assertIn("yandex", calls)

    def test_global_fallback_can_use_any_provider(self):
        config = {
            "provider": "google",
            "fallback_providers": ["brave", "bing"],
        }
        search, calls = _load_search(
            config,
            google_results=[],
            brave_results=["br1"],
            bing_results=["b1"],
        )
        self.assertEqual(search.getresultbyquery("planet"), "br1")
        self.assertEqual(
            search.get_provider_label("planet"), "Brave (fallback for Google)"
        )
        self.assertIn("google", calls)
        self.assertIn("brave", calls)
        self.assertNotIn("bing", calls)

    def test_provider_label_default(self):
        config = {"provider": "yandex"}
        search, _ = _load_search(config)
        self.assertEqual(
            search.get_provider_label("anything"),
            "Yandex (unofficial)",
        )

    def test_clean_query_uses_strip_html(self):
        def strip_html(value):
            return value.replace("<b>", "").replace("</b>", "")

        config = {"provider": "ddg"}
        search, calls = _load_search(config, ddg_results=["d1"], strip_fn=strip_html)
        search.getresultbyquery("<b>cat</b>")
        self.assertEqual(calls.get("ddg"), "cat")

    def test_next_prev_navigation(self):
        config = {"provider": "ddg"}
        search, _ = _load_search(config, ddg_results=["u1", "u2", "u3"])
        self.assertEqual(search.getresultbyquery("q"), "u1")
        self.assertEqual(search.getnextresultbyquery("q"), "u2")
        self.assertEqual(search.getnextresultbyquery("q"), "u3")
        # Stays at last when already at the end
        self.assertEqual(search.getnextresultbyquery("q"), "u3")
        self.assertEqual(search.getprevresultbyquery("q"), "u2")
        self.assertEqual(search.getprevresultbyquery("q"), "u1")
        # Stays at first when already at the beginning
        self.assertEqual(search.getprevresultbyquery("q"), "u1")

    def test_cache_eviction(self):
        config = {"provider": "ddg"}
        search, _ = _load_search(config, ddg_results=["u1"])
        search.MAX_CACHED_QUERIES = 2
        search.getresultbyquery("q1")
        search.getresultbyquery("q2")
        search.getresultbyquery("q3")  # should evict q1
        self.assertNotIn("q1", search.RESULTS)
        self.assertIn("q2", search.RESULTS)
        self.assertIn("q3", search.RESULTS)

    def test_clear_cache_drops_everything(self):
        config = {"provider": "ddg"}
        search, _ = _load_search(config, ddg_results=["u1"])
        search.getresultbyquery("q1")
        search.getresultbyquery("q2")
        self.assertIn("q1", search.RESULTS)
        self.assertIn("q2", search.RESULTS)
        search.clear_cache()
        self.assertEqual(search.RESULTS, {})
        self.assertEqual(search.INDICES, {})
        self.assertEqual(search.PROVIDERS, {})

    def test_clear_cache_then_getresult_uses_new_provider(self):
        """
        After a settings save (which calls clear_cache()), a new search
        must use the freshly-saved provider config, not stale cached
        results from the old change.
        """
        # First, prime the cache with the Yandex provider.
        search, calls = _load_search(
            {"provider": "yandex"},
            yandex_results=["y1"],
            ddg_results=["d1"],
        )
        self.assertEqual(search.getresultbyquery("q"), "y1")
        # Simulate a settings save that switches provider to ddg.
        # We can't easily call SettingsDialog._save_only here, but the
        # contract is: clear_cache() + next getresultbyquery reads
        # the current config.
        from unittest.mock import patch

        # Patch get_config to return the new config
        new_cfg = {"provider": "ddg"}
        with patch.object(
            search.utils, "get_config", return_value=new_cfg
        ):
            search.clear_cache()
            url = search.getresultbyquery("q")
        self.assertEqual(url, "d1")
        self.assertEqual(
            search.get_provider_label("q"), "DuckDuckGo (unofficial)"
        )

    def test_per_provider_fallback_chain(self):
        # Custom chain: when brave returns nothing, fall through to
        # google and then yandex. Verify the right providers are tried
        # in order.
        config = {
            "provider": "brave",
            "fallback_brave": ["google", "yandex"],
        }
        search, calls = _load_search(
            config,
            brave_results=[],
            google_results=[],
            yandex_results=["y1"],
        )
        url = search.getresultbyquery("cat")
        self.assertEqual(url, "y1")
        self.assertIn("brave", calls)
        self.assertIn("google", calls)
        self.assertIn("yandex", calls)

    def test_per_provider_fallback_short_circuits(self):
        # When the first fallback returns a result, the chain stops.
        config = {
            "provider": "brave",
            "fallback_brave": ["google", "yandex"],
        }
        search, calls = _load_search(
            config,
            brave_results=[],
            google_results=["g1"],
            yandex_results=["y1"],
        )
        url = search.getresultbyquery("cat")
        self.assertEqual(url, "g1")
        self.assertIn("brave", calls)
        self.assertIn("google", calls)
        self.assertNotIn("yandex", calls)

    def test_no_fallback_returns_empty_with_primary_label(self):
        config = {
            "provider": "brave",
            "fallback_brave": [],
        }
        search, calls = _load_search(
            config,
            brave_results=[],
            yandex_results=["y1"],
        )
        url = search.getresultbyquery("cat")
        self.assertIsNone(url)
        self.assertIn("brave", calls)
        self.assertNotIn("yandex", calls)

    def test_fallback_string_legacy_format(self):
        # A single string instead of a list should still be accepted.
        config = {
            "provider": "bing",
            "fallback_bing": "yandex",  # legacy: single string
        }
        search, calls = _load_search(
            config,
            bing_results=[],
            yandex_results=["y1"],
        )
        url = search.getresultbyquery("cat")
        self.assertEqual(url, "y1")


if __name__ == "__main__":
    unittest.main()
