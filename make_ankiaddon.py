import os
import zipfile
from pathlib import Path

from new_version import read_manifest_version, bump_version_string, update_version

# Configuration
ADDON_DIR = "addon"
ADDON_SLUG = "Image_Search_v3"


def bump_version() -> str:
    current_version = read_manifest_version(ADDON_DIR)
    new_version = bump_version_string(current_version)
    print(f"Bumping version: {current_version} → {new_version}")
    update_version(new_version, ADDON_DIR)
    return new_version


def create_ankiaddon():
    # Auto-bump version before building
    try:
        version = bump_version()
    except Exception as exc:
        print(f"Warning: Could not auto-bump version: {exc}")
        version = read_manifest_version(ADDON_DIR)

    root_dir = Path.cwd()
    addon_path = root_dir / ADDON_DIR

    if not addon_path.exists():
        print(f"Error: {ADDON_DIR} directory not found.")
        return

    zip_name = f"{ADDON_SLUG}_{version}.zip"
    final_name = f"{ADDON_SLUG}_{version}.ankiaddon"

    # Exclusions
    exclude_dirs = {"__pycache__", ".git", ".vscode", ".github", "tests"}
    exclude_exts = {".ankiaddon", ".pyc"}
    exclude_files = {"meta.json", ".gitignore", ".gitmodules", "mypy.ini"}

    print(f"Creating {final_name} from {ADDON_DIR}...")

    with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(addon_path):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for file in files:
                file_path = Path(root) / file
                if file in exclude_files or file_path.suffix in exclude_exts:
                    continue

                archive_name = file_path.relative_to(addon_path)
                zipf.write(file_path, archive_name)

    # Rename to .ankiaddon
    if os.path.exists(final_name):
        os.remove(final_name)
    os.rename(zip_name, final_name)
    print(f"Successfully created: {final_name}")


if __name__ == "__main__":
    create_ankiaddon()
