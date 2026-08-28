import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class AddonEntrypointTests(unittest.TestCase):
    def test_import_entrypoint_calls_setup(self):
        source = (REPO_ROOT / "addon" / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("def setup()", source)
        self.assertIn("\nsetup()", source)


if __name__ == "__main__":
    unittest.main()
