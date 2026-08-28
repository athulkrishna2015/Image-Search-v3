"""Smoke test: fail the build if any plausible real API key shape
appears in a tracked file. This catches accidental commits of
credentials (Google API keys start with "AIza..." with 39 chars,
Yandex IAM tokens with "AQV..." with ~38 chars, Yandex folder ids
are "b1g..." 20-char strings, Yandex official API keys
"AQVN..." with ~50 chars)."""
import os
import re
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


# Patterns for keys we care about. The point is to flag a real
# credential, not to require an exact match.
_PATTERNS = [
    ("Google API key", re.compile(r"AIza[A-Za-z0-9_-]{20,}")),
    ("Yandex IAM token", re.compile(r"AQV[A-Za-z0-9_-]{30,}")),
    ("Yandex folder id", re.compile(r"\bb1g[A-Za-z0-9_-]{15,}\b")),
    ("Anthropic key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("OpenAI key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
]

# Files we explicitly skip (test fixtures, security docs, etc.).
_SKIP_DIRS = {
    ".git",
    "addon/logs",
    "__pycache__",
}
_SKIP_PATHS = {
    # These files legitimately discuss key patterns.
    Path("doc/SECURITY.md"),
    Path("tests/test_no_keys.py"),
}


def _iter_tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    paths: list[Path] = []
    for line in out.stdout.splitlines():
        if not line:
            continue
        p = REPO_ROOT / line
        if any(part in _SKIP_DIRS for part in p.parts):
            continue
        if p in _SKIP_PATHS:
            continue
        # Only scan text-ish files
        if p.suffix.lower() not in {
            ".py", ".md", ".json", ".yml", ".yaml", ".txt",
            ".cfg", ".ini", ".toml", ".sh",
        }:
            continue
        paths.append(p)
    return paths


class NoRealKeysInRepoTests(unittest.TestCase):
    def test_no_real_api_key_shapes(self):
        offenders: list[tuple[str, str, int, str]] = []
        for path in _iter_tracked_files():
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for label, pattern in _PATTERNS:
                for m in pattern.finditer(text):
                    rel = path.relative_to(REPO_ROOT).as_posix()
                    snippet = m.group(0)
                    # Compute the line number for the report.
                    line = text.count("\n", 0, m.start()) + 1
                    offenders.append((label, rel, line, snippet))
        if offenders:
            msg_lines = [
                "Possible real API key(s) found in tracked files:",
                "",
            ]
            for label, rel, line, snippet in offenders:
                # Mask the middle of the secret.
                masked = (
                    snippet[:4] + "..." + snippet[-4:]
                    if len(snippet) > 12
                    else snippet
                )
                msg_lines.append(f"  {rel}:{line}  ({label}) -> {masked}")
            msg_lines.extend([
                "",
                "These look like real credentials. Move them to "
                "addon/meta.json (which is gitignored) and replace them "
                "with empty strings or dummy values in tracked files.",
                "If a real key has been pushed, ROTATE IT IMMEDIATELY "
                "in the provider's console.",
            ])
            self.fail("\n".join(msg_lines))


if __name__ == "__main__":
    unittest.main()
