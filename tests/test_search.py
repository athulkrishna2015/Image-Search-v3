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


def _load_search(config, ddg_results=None, yandex_results=None, google_results=None, strip_fn=None):
    # Clear prior stubs/modules
    for name in [
        "addon.search",
        "addon.utils",
        "addon.yimages",
        "addon.gimages",
        "addon.ddg_hidden_test",
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

    sys.modules["addon.ddg_hidden_test"] = _make_module(
        "addon.ddg_hidden_test", get_ddg_images=_ddg, getddgimages=_ddg
    )
    sys.modules["addon.yimages"] = _make_module(
        "addon.yimages", get_yimages=_yandex, getyimages=_yandex
    )
    sys.modules["addon.gimages"] = _make_module("addon.gimages", getgimages=_google)

    # Load addon.search without executing addon/__init__.py
    search_path = repo_root / "addon" / "search.py"
    spec = importlib.util.spec_from_file_location("addon.search", search_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["addon.search"] = module
    spec.loader.exec_module(module)
    return module, calls


class SearchProviderTests(unittest.TestCase):
    def test_ddg_fallback_to_yandex_label(self):
        config = {"provider": "duckduckgo"}
        search, calls = _load_search(config, ddg_results=[], yandex_results=["y1"])
        url = search.getresultbyquery("cats")
        self.assertEqual(url, "y1")
        self.assertEqual(search.get_provider_label("cats"), "Yandex (fallback from DuckDuckGo)")
        self.assertEqual(calls.get("ddg"), "cats")
        self.assertEqual(calls.get("yandex"), "cats")

    def test_ddg_primary_label(self):
        config = {"provider": "ddg"}
        search, calls = _load_search(config, ddg_results=["d1", "d2"], yandex_results=["y1"])
        url = search.getresultbyquery("nebula")
        self.assertEqual(url, "d1")
        self.assertEqual(search.get_provider_label("nebula"), "DuckDuckGo")
        self.assertEqual(calls.get("ddg"), "nebula")
        self.assertNotIn("yandex", calls)

    def test_google_fallback_label(self):
        config = {"provider": "google", "google_fallback_to_yandex": True}
        search, calls = _load_search(config, google_results=[], yandex_results=["y1"])
        url = search.getresultbyquery("planet")
        self.assertEqual(url, "y1")
        self.assertEqual(search.get_provider_label("planet"), "Yandex (fallback from Google)")
        self.assertEqual(calls.get("google"), "planet")
        self.assertEqual(calls.get("yandex"), "planet")

    def test_google_no_fallback_label(self):
        config = {"provider": "google", "google_fallback_to_yandex": False}
        search, calls = _load_search(config, google_results=[], yandex_results=["y1"])
        url = search.getresultbyquery("planet")
        self.assertIsNone(url)
        self.assertEqual(search.get_provider_label("planet"), "Google")
        self.assertEqual(calls.get("google"), "planet")
        self.assertNotIn("yandex", calls)

    def test_provider_label_default(self):
        config = {"provider": "yandex"}
        search, _ = _load_search(config)
        self.assertEqual(search.get_provider_label("anything"), "Yandex")

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


if __name__ == "__main__":
    unittest.main()
