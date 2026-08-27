"""Tests for the new 'all' log level, lazy-load semantics, and the
supporter opt-out defensive write."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ADDON_DIR = REPO_ROOT / "addon"


def _load_logger(tmp_log_path: Path):
    for name in list(sys.modules):
        if name == "addon.logger" or name.startswith("addon."):
            del sys.modules[name]
    if "addon" in sys.modules:
        del sys.modules["addon"]

    fake_mw = types.SimpleNamespace(
        addonManager=types.SimpleNamespace(getConfig=lambda _: {})
    )
    aqt = types.ModuleType("aqt")
    aqt.mw = fake_mw
    sys.modules["aqt"] = aqt

    spec = importlib.util.spec_from_file_location("addon.logger", ADDON_DIR / "logger.py")
    mod = importlib.util.module_from_spec(spec)
    mod_src = spec.loader.get_source("addon.logger")
    mod_src = mod_src.replace(
        'LOG_DIR = os.path.join(CURRENT_DIR, "logs")',
        f'LOG_DIR = {str(tmp_log_path.parent)!r}',
    ).replace(
        'LOG_FILE = os.path.join(LOG_DIR, "image_search_v3.log")',
        f'LOG_FILE = {str(tmp_log_path)!r}',
    )
    code = compile(mod_src, str(ADDON_DIR / "logger.py"), "exec")
    spec.loader.exec_module = lambda m: exec(code, mod.__dict__)
    spec.loader.exec_module(mod)
    return mod


class AllLevelTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())
        self.log_path = self.tmp / "image_search_v3.log"
        self.logger_mod = _load_logger(self.log_path)
        self.log = self.logger_mod.log

    def tearDown(self):
        for p in self.tmp.glob("image_search_v3.log*"):
            try:
                p.unlink()
            except Exception:
                pass
        try:
            self.tmp.rmdir()
        except Exception:
            pass

    def test_all_level_is_lowest(self):
        # "all" must be strictly lower than DEBUG so it captures everything.
        self.assertLess(self.logger_mod._LEVELS["all"], self.logger_mod._LEVELS["debug"])
        self.assertLess(self.logger_mod._LEVELS["all"], self.logger_mod._LEVELS["info"])

    def test_set_level_all(self):
        self.log.set_level("all")
        self.assertEqual(self.log.get_level(), "all")

    def test_all_level_captures_debug(self):
        self.log.set_level("all")
        self.log.debug("captured-at-all")
        self.log.info("captured-at-all-info")
        text = self.log_path.read_text(encoding="utf-8")
        self.assertIn("captured-at-all", text)
        self.assertIn("captured-at-all-info", text)

    def test_all_level_captures_below_debug(self):
        # "all" must be the lowest possible level so third-party loggers
        # that emit below DEBUG (e.g. level 1 noise) are also captured.
        import logging
        self.log.set_level("all")
        # Touch the wrapper once to ensure the handler is attached, then
        # emit through the stdlib logger at numeric level 1.
        self.log.info("ensure-handler")
        self.log._logger.log(1, "msg-at-level-1")
        text = self.log_path.read_text(encoding="utf-8")
        self.assertIn("msg-at-level-1", text)

    def test_tail_text_no_unbound_error_when_small(self):
        """Regression test: tail_text used to leave `data` unbound when the
        log file was small, raising UnboundLocalError."""
        self.log.set_level("info")
        self.log.info("small file content")
        # Must not raise.
        text = self.log.tail_text()
        self.assertIn("small file content", text)

    def test_tail_text_truncation_marker_present(self):
        self.log.set_level("info")
        # Write enough to force truncation.
        with open(self.log_path, "w", encoding="utf-8") as fh:
            fh.write("X" * 200_000)
        text = self.log.tail_text(max_bytes=1024)
        self.assertIn("[truncated]", text)


class SupporterOptOutDefensiveTests(unittest.TestCase):
    """The mixin must not crash when addonManager.writeAddonMeta raises
    FileNotFoundError (e.g. when the addon folder is symlinked under a
    different name than the package id)."""

    def setUp(self):
        for name in list(sys.modules):
            if name.startswith("addon."):
                del sys.modules[name]
        if "addon" in sys.modules:
            del sys.modules["addon"]

        # The mixin imports aqt.qt symbols; stub the bare minimum to
        # allow the module to import.
        aqt_qt = types.ModuleType("aqt.qt")
        aqt_qt.QApplication = type("QApplication", (), {"clipboard": staticmethod(lambda: None)})
        aqt_qt.Qt = types.SimpleNamespace(
            TextSelectableByMouse=1,
            TextFormat=types.SimpleNamespace(RichText=0),
            AlignmentFlag=types.SimpleNamespace(AlignCenter=0, AlignHCenter=0),
            AspectRatioMode=types.SimpleNamespace(KeepAspectRatio=0),
            TransformationMode=types.SimpleNamespace(SmoothTransformation=0),
            CursorShape=types.SimpleNamespace(PointingHandCursor=0),
        )
        aqt_qt.QCheckBox = type("QCheckBox", (), {})
        aqt_qt.QHBoxLayout = type("QHBoxLayout", (), {})
        aqt_qt.QLabel = type("QLabel", (), {})
        aqt_qt.QLineEdit = type("QLineEdit", (), {})
        aqt_qt.QPushButton = type("QPushButton", (), {})
        aqt_qt.QScrollArea = type("QScrollArea", (), {})
        aqt_qt.QVBoxLayout = type("QVBoxLayout", (), {})
        aqt_qt.QWidget = type("QWidget", (), {})
        aqt_qt.QPixmap = type("QPixmap", (), {})
        aqt_qt.QTimer = type("QTimer", (), {"singleShot": staticmethod(lambda *a, **k: None)})
        aqt = types.ModuleType("aqt")
        aqt.qt = aqt_qt
        aqt_webview = types.ModuleType("aqt.webview")
        aqt_webview.AnkiWebView = type("AnkiWebView", (), {})
        aqt.webview = aqt_webview
        aqt_utils = types.ModuleType("aqt.utils")
        aqt_utils.openLink = lambda *a, **k: None
        aqt.utils = aqt_utils
        sys.modules["aqt"] = aqt
        sys.modules["aqt.qt"] = aqt_qt
        sys.modules["aqt.webview"] = aqt_webview
        sys.modules["aqt.utils"] = aqt_utils

        # Build a fake mw that raises FileNotFoundError on writeAddonMeta
        # but returns an empty dict for addonMeta.
        self.meta = {}
        self.write_calls = []

        def addonMeta(_pkg):
            return self.meta

        def writeAddonMeta(_pkg, m):
            self.write_calls.append(m)
            raise FileNotFoundError("simulated meta dir missing")

        aqt.mw = types.SimpleNamespace(
            addonManager=types.SimpleNamespace(
                addonMeta=addonMeta,
                writeAddonMeta=writeAddonMeta,
            )
        )

        # Logger stub
        log_mod = types.ModuleType("addon.logger")
        log_mod.log = types.SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            error=lambda *a, **k: None,
            debug=lambda *a, **k: None,
        )

        # Tabs stubs (we only need widgets for ADDON_PACKAGE)
        addon_pkg = types.ModuleType("addon")
        addon_pkg.__path__ = [str(ADDON_DIR)]
        tabs_pkg = types.ModuleType("addon.tabs")
        tabs_pkg.__path__ = [str(ADDON_DIR / "tabs")]
        widgets_mod = types.ModuleType("addon.tabs.widgets")
        widgets_mod.ADDON_PACKAGE = "178037783"
        sys.modules["addon"] = addon_pkg
        sys.modules["addon.tabs"] = tabs_pkg
        sys.modules["addon.tabs.widgets"] = widgets_mod
        tabs_pkg.ADDON_PACKAGE = "178037783"
        sys.modules["addon.logger"] = log_mod
        addon_pkg.logger = log_mod
        addon_pkg.tabs = tabs_pkg

        # Now load the mixin.
        spec = importlib.util.spec_from_file_location(
            "addon.tabs.tab_support", ADDON_DIR / "tabs" / "tab_support.py"
        )
        self.mixin_mod = importlib.util.module_from_spec(spec)
        sys.modules["addon.tabs.tab_support"] = self.mixin_mod
        spec.loader.exec_module(self.mixin_mod)

    def test_load_supporter_state_tolerates_failure(self):
        # The mixin should at minimum not raise.
        class _FakeCheck:
            def __init__(self):
                self.value = False
                self.blocked = False
            def blockSignals(self, v):
                self.blocked = v
            def setChecked(self, v):
                self.value = v

        class _Host:
            def __init__(self):
                self.supporter_check = _FakeCheck()

        host = _Host()
        # If addonMeta returns a dict with no supporter_opt_out, setChecked(False)
        self.meta = {}
        self.mixin_mod.SupportTabMixin.load_supporter_state(host)
        self.assertFalse(host.supporter_check.value)

    def test_on_supporter_check_toggled_does_not_raise(self):
        class _FakeCheck:
            def __init__(self):
                self.value = False
            def blockSignals(self, v):
                self.blocked = v
            def setChecked(self, v):
                self.value = v

        class _Host:
            def __init__(self):
                self.supporter_check = _FakeCheck()

        host = _Host()
        # Must not raise even though writeAddonMeta raises FileNotFoundError.
        try:
            self.mixin_mod.SupportTabMixin.on_supporter_check_toggled(host, True)
        except FileNotFoundError:
            self.fail("on_supporter_check_toggled raised FileNotFoundError")


if __name__ == "__main__":
    unittest.main()
