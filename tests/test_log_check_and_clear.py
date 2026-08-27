"""Tests for the new 'check log file' scanner, clear-on-startup
behaviour, and the non-modal settings dialog."""
import importlib.util
import inspect
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
    spec.loader.exec_module = lambda m: exec(code, m.__dict__)
    spec.loader.exec_module(mod)
    return mod


class CheckLogFileTests(unittest.TestCase):
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

    def test_missing_file(self):
        report = self.log.check_log_file()
        self.assertFalse(report["exists"])
        self.assertEqual(report["findings"], [])

    def test_no_findings_clean_log(self):
        self.log.set_level("info")
        self.log.info("everything is fine")
        self.log.info("another info line")
        report = self.log.check_log_file()
        self.assertTrue(report["exists"])
        self.assertEqual(report["size_bytes"], self.log_path.stat().st_size)
        self.assertEqual(report["line_count"], 2)
        self.assertEqual(report["findings"], [])

    def test_finds_traceback(self):
        self.log.set_level("info")
        self.log.info("Traceback (most recent call last):")
        self.log.info('  File "foo.py", line 1, in <module>')
        self.log.info("ValueError: bad")
        report = self.log.check_log_file()
        cats = {f["category"] for f in report["findings"]}
        self.assertIn("Traceback", cats)

    def test_finds_timeout(self):
        self.log.set_level("info")
        self.log.info("requests: read timeout")
        report = self.log.check_log_file()
        cats = {f["category"] for f in report["findings"]}
        self.assertIn("Timeout", cats)

    def test_finds_provider_failures(self):
        self.log.set_level("info")
        self.log.info("yimages: giving up query='foo'")
        self.log.info("ddg: no vqd for 'bar'")
        report = self.log.check_log_file()
        cats = {f["category"] for f in report["findings"]}
        self.assertIn("yimages giving up", cats)
        self.assertIn("ddg giving up", cats)

    def test_finds_settings_save_failure(self):
        self.log.set_level("info")
        self.log.error("Settings save failed: %r", ValueError("x"))
        report = self.log.check_log_file()
        cats = {f["category"] for f in report["findings"]}
        self.assertIn("Settings save failed", cats)

    def test_sample_is_capped(self):
        self.log.set_level("info")
        long_line = "X" * 1000
        self.log.info("Traceback (most recent call last): %s", long_line)
        report = self.log.check_log_file()
        for f in report["findings"]:
            self.assertLessEqual(len(f["sample"]), 240)

    def test_truncation_marker(self):
        # Write more than the scan cap, then check.
        with open(self.log_path, "w", encoding="utf-8") as fh:
            fh.write("a" * 500_000)
        report = self.log.check_log_file(max_bytes=8 * 1024)
        self.assertIn("checked_bytes_note", report)
        # The "all is well" check should not flag plain ASCII text.
        self.assertEqual(report["findings"], [])


class MaybeClearOnStartupTests(unittest.TestCase):
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

    def test_default_clears(self):
        self.log.info("old content")
        self.assertTrue(self.log.maybe_clear_on_startup(None))
        self.assertEqual(self.log_path.read_text(encoding="utf-8"), "")

    def test_disabled_does_not_clear(self):
        self.log.info("old content")
        ok = self.log.maybe_clear_on_startup({"clear_logs_on_startup": False})
        self.assertFalse(ok)
        text = self.log_path.read_text(encoding="utf-8")
        self.assertIn("old content", text)

    def test_explicit_true_clears(self):
        self.log.info("old content")
        ok = self.log.maybe_clear_on_startup({"clear_logs_on_startup": True})
        self.assertTrue(ok)
        self.assertEqual(self.log_path.read_text(encoding="utf-8"), "")

    def test_missing_file_does_not_create(self):
        # No log file yet. Should not create one.
        self.assertFalse(self.log_path.exists())
        ok = self.log.maybe_clear_on_startup(None)
        self.assertFalse(ok)
        self.assertFalse(self.log_path.exists())


class NonModalDialogTests(unittest.TestCase):
    def test_settings_dialog_does_not_use_exec(self):
        """
        Regression: the settings dialog used to call `dlg.exec()` which
        blocks the Anki main window. We now use `show()` so the user
        can keep editing in Anki.
        """
        ui_menu_src = (REPO_ROOT / "addon" / "ui_menu.py").read_text(
            encoding="utf-8"
        )
        # Allow ".exec_module(" (used by importlib); forbid "dlg.exec("
        # and similar blocking patterns.
        import re
        cleaned = re.sub(r"\bexec_module\b", "", ui_menu_src)
        for forbidden in ("dlg.exec(", "dialog.exec(", "self.exec("):
            self.assertNotIn(forbidden, cleaned, f"Found blocking call: {forbidden!r}")
        # Sanity: the entry point must call show() on the dialog.
        self.assertTrue(
            "_DIALOG_INST.show()" in cleaned
            or "dlg.show()" in cleaned
            or ".show()" in cleaned,
            "settings_dialog() should call .show() on the dialog instance",
        )
        self.assertIn("setWindowModality", cleaned)
        self.assertIn("Qt.WindowModality.NonModal", cleaned)


if __name__ == "__main__":
    unittest.main()
