import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class AddonEntrypointTests(unittest.TestCase):
    def test_import_entrypoint_calls_setup(self):
        source = (REPO_ROOT / "addon" / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("def setup()", source)
        self.assertIn("\nsetup()", source)

    def test_support_welcome_selects_scroll_tab(self):
        source = (REPO_ROOT / "addon" / "ui_menu.py").read_text(encoding="utf-8")
        self.assertIn("self.support_scroll = QScrollArea(self)", source)
        self.assertIn("self.tabs.setCurrentWidget(self.support_scroll)", source)
        self.assertNotIn("self.tabs.setCurrentWidget(self.support_tab)", source)

    def test_update_welcome_is_scheduled_after_menu_setup(self):
        source = (REPO_ROOT / "addon" / "ui_menu.py").read_text(encoding="utf-8")
        self.assertIn("QTimer.singleShot(_UPDATE_WELCOME_DELAY_MS, _show_update_welcome)", source)
        self.assertIn("_UPDATE_WELCOME_DELAY_MS = 1500", source)
        self.assertIn("_schedule_update_welcome()", source)
        self.assertIn("settings_dialog()", source)


if __name__ == "__main__":
    unittest.main()
