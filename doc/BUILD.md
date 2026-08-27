# Build & Packaging

The repo includes two helper scripts at the top level:

| Script | What it does |
| --- | --- |
| `bump.py` | Reads `addon/manifest.json`, increments the minor component, and writes the new version into `addon/manifest.json` and `addon/VERSION`. |
| `new_version.py` | Lower-level: `read_manifest_version`, `bump_version_string`, `update_version`. Used by `bump.py` and `make_ankiaddon.py`. |
| `make_ankiaddon.py` | Auto-bumps the version, then zips `addon/` (minus excluded paths) into `<slug>_<version>.ankiaddon`. |

## Version scheme

`3.<major>.<minor>`. The leading `3` is fixed and matches the Anki
add-on's public package id `178037783`. Bumping is enforced by
`new_version._VERSION_RE`; any other shape raises `ValueError`.

## Excluded paths inside the .ankiaddon

From `make_ankiaddon.py`:

- **Dirs:** `__pycache__`, `.git`, `.vscode`, `.github`, `tests`
- **Exts:** `.ankiaddon`, `.pyc`
- **Files:** `meta.json`, `.gitignore`, `.gitmodules`, `mypy.ini`

This is what keeps `meta.json` (user state) and the build artifacts
themselves out of the distribution.

## Building locally

```bash
# Bump and package
python3 make_ankiaddon.py

# Only bump, no package
python3 bump.py
```

The result is `Image_Search_v3_<version>.ankiaddon` in the repo root.

## Manual install (for testing)

In Anki: **Tools → Add-ons → Install from file** and pick the
`.ankiaddon`. Or drop it into your Anki add-ons folder
(`~/Library/Application Support/Anki2/addons21/` on macOS,
`%APPDATA%\Anki2\addons21\` on Windows, `~/.local/share/Anki2/addons21/`
on Linux).

## Publishing a release

1. Bump the version (`python3 bump.py` or `make_ankiaddon.py`).
2. Commit + push.
3. Tag the commit: `git tag v3.X.Y && git push origin v3.X.Y`.
4. The GitHub Actions release workflow (if present) or a manual
   upload to the GitHub Releases page.

The release asset **must** be the `.ankiaddon` produced by
`make_ankiaddon.py` — AnkiWeb's "Update" button fetches that asset.
