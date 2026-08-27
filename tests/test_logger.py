import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ADDON_DIR = REPO_ROOT / "addon"


def _load_logger(tmp_log_path: Path):
    """
    Load addon.logger with a redirected log path so the test does not
    touch the user's real log file.
    """
    for name in list(sys.modules):
        if name == "addon.logger" or name.startswith("addon."):
            del sys.modules[name]
    if "addon" in sys.modules:
        del sys.modules["addon"]

    # Patch os.path.dirname to point at the tmp file.
    fake_mw = types.SimpleNamespace(
        addonManager=types.SimpleNamespace(getConfig=lambda _: {})
    )
    aqt = types.ModuleType("aqt")
    aqt.mw = fake_mw
    sys.modules["aqt"] = aqt

    spec = importlib.util.spec_from_file_location("addon.logger", ADDON_DIR / "logger.py")
    mod = importlib.util.module_from_spec(spec)

    # Replace the module's LOG_DIR/LOG_FILE before exec_module so
    # _ensure_handler uses our temp path.
    mod_src = spec.loader.get_source("addon.logger")
    mod_src = mod_src.replace(
        'LOG_DIR = os.path.join(CURRENT_DIR, "logs")',
        f'LOG_DIR = {str(tmp_log_path.parent)!r}',
    ).replace(
        'LOG_FILE = os.path.join(LOG_DIR, "image_search_v3.log")',
        f'LOG_FILE = {str(tmp_log_path)!r}',
    )
    code = compile(mod_src, str(ADDON_DIR / "logger.py"), "exec")
    spec.loader.exec_module = lambda m: exec(code, mod.__dict__)  # type: ignore[assignment]
    spec.loader.exec_module(mod)
    return mod


class LoggerTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())
        self.log_path = self.tmp / "image_search_v3.log"
        self.logger_mod = _load_logger(self.log_path)
        self.log = self.logger_mod.log

    def tearDown(self):
        # Wipe the rotated files we may have created.
        for p in self.tmp.glob("image_search_v3.log*"):
            try:
                p.unlink()
            except Exception:
                pass
        try:
            self.tmp.rmdir()
        except Exception:
            pass

    def test_default_level(self):
        self.assertEqual(self.log.get_level(), "info")

    def test_set_level(self):
        self.log.set_level("debug")
        self.assertEqual(self.log.get_level(), "debug")
        self.log.set_level("error")
        self.assertEqual(self.log.get_level(), "error")

    def test_set_level_rejects_invalid(self):
        self.log.set_level("info")
        self.log.set_level("notalevel")  # not in _LEVELS
        self.assertEqual(self.log.get_level(), "info")

    def test_log_file_created(self):
        self.log.info("hello world")
        self.assertTrue(self.log_path.exists())
        text = self.log_path.read_text(encoding="utf-8")
        self.assertIn("hello world", text)
        self.assertIn("INFO", text)
        self.assertIn("image_search_v3", text)

    def test_log_level_filters(self):
        self.log.set_level("warning")
        self.log.info("should not appear")
        self.log.warning("should appear")
        text = self.log_path.read_text(encoding="utf-8")
        self.assertNotIn("should not appear", text)
        self.assertIn("should appear", text)

    def test_clear(self):
        self.log.info("before clear")
        self.assertTrue(self.log_path.exists())
        ok = self.log.clear()
        self.assertTrue(ok)
        text = self.log_path.read_text(encoding="utf-8")
        self.assertNotIn("before clear", text)
        self.assertEqual(text, "")

    def test_tail_text_truncates(self):
        # Write more than the default cap.
        big = "x" * 200_000
        self.log.info(big)
        text = self.log.tail_text(max_bytes=1024)
        # Marker is shown when truncated.
        self.assertIn("[truncated]", text)
        # The full payload is no longer present.
        self.assertNotIn(big, text)

    def test_tail_text_handles_missing_file(self):
        # File does not exist yet; should return "" not raise.
        self.assertFalse(self.log_path.exists())
        self.assertEqual(self.log.tail_text(), "")

    def test_log_path_uses_addon_dir(self):
        # Sanity: the public constants point somewhere stable.
        self.assertTrue(self.logger_mod.LOGGER_NAME)
        self.assertTrue(self.logger_mod.LOG_DIR)


if __name__ == "__main__":
    unittest.main()
