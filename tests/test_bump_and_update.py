import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_addon(tmp: Path, version: str) -> Path:
    """
    Create a fake addon directory with manifest.json + VERSION.
    Returns the addon path.
    """
    addon = tmp / "addon"
    addon.mkdir(parents=True, exist_ok=True)
    (addon / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    (addon / "manifest.json").write_text(
        json.dumps({"version": version, "name": "test"}),
        encoding="utf-8",
    )
    return addon


class BumpTests(unittest.TestCase):
    def setUp(self):
        # Reload bump.py fresh each test.
        for name in list(sys.modules):
            if name == "bump":
                del sys.modules[name]
        self.bump = _load_module("bump", REPO_ROOT / "bump.py")

    def test_validate_version_normalizes(self):
        self.assertEqual(self.bump.validate_version("3.11.2"), "3.11.2")
        self.assertEqual(self.bump.validate_version("  3.11.2  "), "3.11.2")

    def test_validate_version_rejects_garbage(self):
        with self.assertRaises(ValueError):
            self.bump.validate_version("not-a-version")
        with self.assertRaises(ValueError):
            self.bump.validate_version("")
        with self.assertRaises(ValueError):
            self.bump.validate_version("3")

    def test_increment_patch(self):
        self.assertEqual(self.bump.increment_version("3.11.2", "patch"), "3.11.3")
        self.assertEqual(self.bump.increment_version("3.11.9", "patch"), "3.11.10")

    def test_increment_minor(self):
        self.assertEqual(self.bump.increment_version("3.11.2", "minor"), "3.12")

    def test_increment_major(self):
        self.assertEqual(self.bump.increment_version("3.11.2", "major"), "4.0")

    def test_normalize_bump_part_alias(self):
        self.assertEqual(self.bump.normalize_bump_part("path"), "patch")
        self.assertEqual(self.bump.normalize_bump_part("PATCH"), "patch")
        with self.assertRaises(ValueError):
            self.bump.normalize_bump_part("nope")

    def test_read_current_version(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            addon = _make_addon(Path(d), "3.11.2")
            self.assertEqual(self.bump.read_current_version(addon), "3.11.2")

    def test_sync_version(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            addon = _make_addon(Path(d), "3.11.2")
            self.bump.sync_version("3.12.0", addon)
            self.assertEqual(
                (addon / "VERSION").read_text(encoding="utf-8").strip(),
                "3.12.0",
            )
            manifest = json.loads((addon / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["version"], "3.12.0")

    def test_bump_version_end_to_end(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            addon = _make_addon(Path(d), "3.11.2")
            rc = self.bump.bump_version(addon, "patch")
            self.assertEqual(rc, 0)
            self.assertEqual(self.bump.read_current_version(addon), "3.11.3")
            rc = self.bump.bump_version(addon, "minor")
            self.assertEqual(rc, 0)
            self.assertEqual(self.bump.read_current_version(addon), "3.12")


class UpdateCheckTests(unittest.TestCase):
    def setUp(self):
        # Backup the real manifest so we can restore it after the test,
        # regardless of which version we wrote.
        self._manifest_backup = (
            (REPO_ROOT / "addon" / "manifest.json").read_text(encoding="utf-8")
        )
        # Stub aqt.mw with an in-memory meta dict.
        self._meta = {}
        fake_mw = types.SimpleNamespace(
            addonManager=types.SimpleNamespace(
                addonMeta=lambda _pkg: self._meta,
                writeAddonMeta=lambda _pkg, m: self._meta.update(m),
            )
        )
        aqt = types.ModuleType("aqt")
        aqt.mw = fake_mw
        sys.modules["aqt"] = aqt

        # The tabs package transitively imports aqt.qt symbols. Stub the
        # widget constants update_check actually needs (ADDON_PACKAGE).
        # We avoid importing the whole tabs package.
        if "addon" in sys.modules:
            del sys.modules["addon"]
        addon_pkg = types.ModuleType("addon")
        addon_pkg.__path__ = [str(REPO_ROOT / "addon")]
        sys.modules["addon"] = addon_pkg

        if "addon.tabs" in sys.modules:
            del sys.modules["addon.tabs"]
        tabs_pkg = types.ModuleType("addon.tabs")
        tabs_pkg.__path__ = [str(REPO_ROOT / "addon" / "tabs")]
        sys.modules["addon.tabs"] = tabs_pkg

        if "addon.tabs.widgets" in sys.modules:
            del sys.modules["addon.tabs.widgets"]
        widgets_mod = types.ModuleType("addon.tabs.widgets")
        widgets_mod.ADDON_PACKAGE = "178037783"
        sys.modules["addon.tabs.widgets"] = widgets_mod
        tabs_pkg.ADDON_PACKAGE = "178037783"
        addon_pkg.tabs = tabs_pkg

        if "addon.update_check" in sys.modules:
            del sys.modules["addon.update_check"]
        if "addon.logger" in sys.modules:
            del sys.modules["addon.logger"]

        # Minimal logger stub
        log_mod = types.ModuleType("addon.logger")
        log_mod.log = types.SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            error=lambda *a, **k: None,
            debug=lambda *a, **k: None,
        )
        sys.modules["addon.logger"] = log_mod
        addon_pkg.logger = log_mod

        self.uc = _load_module("addon.update_check", REPO_ROOT / "addon" / "update_check.py")

    def _set_version(self, v: str):
        (REPO_ROOT / "addon" / "manifest.json").write_text(
            json.dumps({"version": v, "name": "x"}), encoding="utf-8"
        )

    def tearDown(self):
        # Restore manifest to its original content.
        (REPO_ROOT / "addon" / "manifest.json").write_text(
            self._manifest_backup, encoding="utf-8"
        )
        # Don't leak meta across tests.
        self._meta.clear()

    def test_current_version(self):
        self._set_version("3.11.2")
        self.assertEqual(self.uc.current_version(), "3.11.2")

    def test_first_open_after_update_returns_true(self):
        self._set_version("3.11.3")
        self._meta.clear()  # no last_support_welcome_version
        self.assertTrue(
            self.uc.should_show_support_welcome({"auto_show_support_on_update": True})
        )

    def test_same_version_returns_false(self):
        self._set_version("3.11.3")
        self._meta["last_support_welcome_version"] = "3.11.3"
        self.assertFalse(
            self.uc.should_show_support_welcome({"auto_show_support_on_update": True})
        )

    def test_user_disabled_returns_false(self):
        self._set_version("3.11.3")
        self._meta.clear()
        self.assertFalse(
            self.uc.should_show_support_welcome({"auto_show_support_on_update": False})
        )

    def test_supporter_opt_out_returns_false(self):
        self._set_version("3.11.3")
        self._meta["supporter_opt_out"] = True
        self.assertFalse(
            self.uc.should_show_support_welcome({"auto_show_support_on_update": True})
        )

    def test_mark_support_welcomed_persists(self):
        self._set_version("3.11.3")
        self._meta.clear()
        self.uc.mark_support_welcomed()
        self.assertEqual(self._meta.get("last_support_welcome_version"), "3.11.3")
        # And the next check returns False.
        self.assertFalse(
            self.uc.should_show_support_welcome({"auto_show_support_on_update": True})
        )

    def test_does_not_touch_startup(self):
        """
        The function only reads the manifest on call; it does not register
        timers, hooks, or threads. We assert by inspection: should_show_
        support_welcome's body has no side effects beyond dict lookups.
        """
        import inspect
        src = inspect.getsource(self.uc.should_show_support_welcome)
        self.assertNotIn("QTimer", src)
        self.assertNotIn("addHook", src)
        self.assertNotIn("threading", src)


if __name__ == "__main__":
    unittest.main()
