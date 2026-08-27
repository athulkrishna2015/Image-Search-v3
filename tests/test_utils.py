import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ADDON_DIR = REPO_ROOT / "addon"


def _load_module(name, path, **extra_attrs):
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    for k, v in extra_attrs.items():
        setattr(mod, k, v)
    spec.loader.exec_module(mod)
    return mod


def _load_utils():
    # Build minimal stubs so addon.utils can import without Anki.
    fake_mw = types.SimpleNamespace(
        addonManager=types.SimpleNamespace(getConfig=lambda _name: {})
    )
    aqt = types.ModuleType("aqt")
    aqt.mw = fake_mw
    sys.modules["aqt"] = aqt
    return _load_module("addon.utils", ADDON_DIR / "utils.py")


def _load_ui_editor():
    fake_mw = types.SimpleNamespace(
        addonManager=types.SimpleNamespace(getConfig=lambda _name: {})
    )
    aqt = types.ModuleType("aqt")
    aqt.mw = fake_mw
    sys.modules["aqt"] = aqt

    anki_hooks = types.ModuleType("anki.hooks")
    anki_hooks.addHook = lambda *a, **k: None
    sys.modules.setdefault("anki", types.ModuleType("anki"))
    sys.modules["anki.hooks"] = anki_hooks
    return _load_module("addon.ui_editor", ADDON_DIR / "ui_editor.py")


class InferSuffixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.utils = _load_utils()

    def test_common_extensions(self):
        for url, ext in [
            ("https://x/a.JPG", ".jpg"),
            ("https://x/a.PNG", ".png"),
            ("https://x/a.gif?ver=1", ".gif"),
            ("https://x/path/foo.WebP", ".webp"),
            ("https://x/foo.bmp", ".bmp"),
        ]:
            self.assertEqual(self.utils._infer_suffix_from_url(url), ext, url)

    def test_unknown_defaults_to_jpg(self):
        self.assertEqual(
            self.utils._infer_suffix_from_url("https://x/noext?token=1"),
            ".jpg",
        )

    def test_handles_garbage(self):
        self.assertEqual(self.utils._infer_suffix_from_url(""), ".jpg")
        self.assertEqual(self.utils._infer_suffix_from_url(None), ".jpg")  # type: ignore[arg-type]


class ImageTagTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.utils = _load_utils()

    def test_basic(self):
        self.assertEqual(
            self.utils.image_tag("pic.jpg"),
            '<img src="pic.jpg" class="imgsearch">',
        )

    def test_escapes_quotes(self):
        tag = self.utils.image_tag('evil"name.jpg')
        self.assertNotIn('"name.jpg', tag)
        self.assertIn("&quot;", tag)
        self.assertIn('class="imgsearch"', tag)

    def test_handles_none(self):
        self.assertIn('class="imgsearch"', self.utils.image_tag(None))


class SafePrefixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.utils = _load_utils()

    def test_default_when_empty(self):
        self.assertEqual(self.utils._safe_prefix(""), "img_")

    def test_strips_path_separators(self):
        self.assertEqual(self.utils._safe_prefix("../../etc/passwd"), "etcpasswd_")

    def test_keeps_safe_chars(self):
        self.assertEqual(self.utils._safe_prefix("abc-12_x"), "abc-12_x_")

    def test_caps_length(self):
        out = self.utils._safe_prefix("a" * 200)
        self.assertTrue(out.endswith("_"))
        self.assertLessEqual(len(out.rstrip("_")), 32)


class ReplaceLastImgsearchTagTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.editor = _load_ui_editor()

    def test_replaces_last_imgsearch(self):
        html = (
            'before <img class="imgsearch" src="a.jpg"> mid '
            '<img class="imgsearch" src="b.jpg"> after'
        )
        new = self.editor._replace_last_imgsearch_tag(html, '<img src="c.jpg" class="imgsearch">')
        self.assertIsNotNone(new)
        self.assertIn('src="c.jpg"', new)
        self.assertNotIn('src="b.jpg"', new)
        self.assertIn('src="a.jpg"', new)  # first one kept

    def test_no_match_returns_none(self):
        self.assertIsNone(
            self.editor._replace_last_imgsearch_tag(
                '<img src="x.jpg">',
                '<img src="y.jpg" class="imgsearch">',
            )
        )

    def test_preserves_other_images(self):
        html = 'text <img src="user.jpg"> more'
        new = self.editor._replace_last_imgsearch_tag(html, '<img src="n.jpg" class="imgsearch">')
        self.assertIsNone(new)  # smart replace never touches non-imgsearch images


class LruTouchOnNavTests(unittest.TestCase):
    def test_next_and_prev_refresh_recency(self):
        # Reuse the existing search-loader pattern.
        sys.path.insert(0, str(REPO_ROOT))
        from tests.test_search import _load_search  # type: ignore

        search, _ = _load_search(
            {"provider": "ddg"},
            ddg_results=["u1", "u2", "u3"],
        )
        search.MAX_CACHED_QUERIES = 2

        search.getresultbyquery("q1")
        search.getresultbyquery("q2")

        # Touch q1 via next/prev → should become MRU
        search.getnextresultbyquery("q1")
        search.getprevresultbyquery("q1")

        # Adding q3 should evict q2 (oldest after touch)
        search.getresultbyquery("q3")

        self.assertIn("q1", search.RESULTS)
        self.assertIn("q3", search.RESULTS)
        self.assertNotIn("q2", search.RESULTS)


class SearchTouchOnEmptyCacheTests(unittest.TestCase):
    def test_next_when_cache_empty_does_not_insert(self):
        sys.path.insert(0, str(REPO_ROOT))
        from tests.test_search import _load_search  # type: ignore

        search, _ = _load_search({"provider": "ddg"}, ddg_results=["u1"])
        # No prior getresultbyquery → cache empty for "q"
        result = search.getnextresultbyquery("q")
        self.assertIsNone(result)
        self.assertNotIn("q", search.RESULTS)


if __name__ == "__main__":
    unittest.main()
