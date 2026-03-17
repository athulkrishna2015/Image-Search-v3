import json
import re
import sys
from pathlib import Path

_VERSION_RE = re.compile(r"^3\.(\d+)\.(\d+)$")


def _normalize_version(version: str) -> str:
    version = (version or "").strip()
    if version.startswith("v"):
        version = version[1:]
    if not _VERSION_RE.match(version):
        raise ValueError(
            "Version must follow 3.<major>.<minor> (e.g., 3.7.0). "
            "The leading 3 is fixed."
        )
    return version


def read_manifest_version(addon_dir: str) -> str:
    manifest_file = Path(addon_dir) / "manifest.json"
    if not manifest_file.exists():
        raise FileNotFoundError(f"{manifest_file} not found")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    return (manifest.get("version") or "").strip()


def bump_version_string(current_version: str) -> str:
    normalized = _normalize_version(current_version)
    _, major, minor = normalized.split(".")
    new_minor = int(minor) + 1
    return f"3.{int(major)}.{new_minor}"


def update_version(new_version: str, addon_dir: str) -> str:
    normalized = _normalize_version(new_version)

    version_file = Path(addon_dir) / "VERSION"
    if version_file.exists():
        version_file.write_text(normalized)
        print(f"Updated {version_file}")

    manifest_file = Path(addon_dir) / "manifest.json"
    if manifest_file.exists():
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        manifest["version"] = normalized
        manifest_file.write_text(json.dumps(manifest, indent=4), encoding="utf-8")
        print(f"Updated {manifest_file}")

    return normalized


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python new_version.py <new_version> <addon_dir>")
        sys.exit(1)

    try:
        update_version(sys.argv[1], sys.argv[2])
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)
