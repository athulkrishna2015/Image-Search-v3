# Build & Packaging

The repo includes two helper scripts at the top level:

| Script | What it does |
| --- | --- |
| `bump.py` | Reads `addon/manifest.json` and `addon/VERSION`, increments the chosen part (default `patch`), and writes the new version back to both files. CLI: `python3 bump.py [major|minor|patch]`. |
| `make_ankiaddon.py` | Calls `bump.bump_version` to bump the patch version, then zips `addon/` (minus the patterns in `.gitignore` and a few hard-coded local-state files) into `<slug>_v<version>_<timestamp>.ankiaddon`. CLI: `python3 make_ankiaddon.py [VERSION] [--clean]`. |

## Version scheme

`3.<major>.<minor>` for the Anki add-on's display version, where the
leading `3` is fixed and matches the Anki add-on's public package id
`178037783`. The build script writes both `addon/manifest.json` and
`addon/VERSION` and stores `human_version` alongside `version` in
the manifest for AnkiWeb.

## Excluded paths inside the .ankiaddon

`make_ankiaddon.py` reads `.gitignore` at the repo root and uses
its patterns (plus a few hard-coded runtime files) to decide which
paths to skip. As of this writing:

- **From `.gitignore`:** `__pycache__/`, `.git/`, `.vscode/`,
  `meta.json`, `addon/meta.json`, `addon/logs/`, `*.log`,
  `*.ankiaddon`, `venv/`, `.venv/`, `env/`, `.env`, `*.pyc`,
  `*.py[cod]`, etc.
- **Hard-coded in the script** (in addition to the gitignore filter):
  `meta.json`, `batch_state.json`, `blacklist.json`, anything ending
  in `.log` or matching `*.log.*`.

This is what keeps `meta.json` (user state, possibly with secrets),
`addon/logs/` (rotating log files), and build artifacts out of the
distribution. `config.json` is always included.

## Building locally

```bash
# Bump patch and package (default)
python3 make_ankiaddon.py

# Bump with a specific part (writes to manifest.json / VERSION)
python3 bump.py patch        # default
python3 bump.py minor
python3 bump.py major

# Package a specific version without bumping
python3 make_ankiaddon.py 3.12.0

# Remove old .ankiaddon files first
python3 make_ankiaddon.py --clean
```

The result is `<addon_name>_v<version>_<timestamp>.ankiaddon` in the
repo root (e.g. `Image_Search_v3_v3.12.0_202608280136.ankiaddon`).
Older packages are kept on disk unless `--clean` is passed.

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

## Local development (symlink)

The fastest way to iterate is to symlink `addon/` directly into
Anki's add-ons folder so edits show up after restarting Anki (or
"Reload" via **Tools → Add-ons**).

**Important:** for best compatibility, name the symlink the same way
Anki loads the add-on package in that environment. If the checkout is
mounted as `addon`, Anki will use `addonManager.addonMeta("addon")`
and `writeAddonMeta("addon", …)`. If you install the zip into the
normal Anki add-ons folder, the package id is `178037783` and the
numeric path is used instead.

The helper functions in `addon/update_check.py` now tolerate both
forms: they prefer Anki-managed metadata when the package name is
numeric, and fall back to local `addon/meta.json` reads/writes in a
development checkout so the logs stay quiet.

**Linux / macOS:**

```shell
ln -s "$(pwd)/addon" "$HOME/.local/share/Anki2/addons21/178037783"
```

**Windows (Admin PowerShell):**

```powershell
New-Item -ItemType SymbolicLink `
    -Path "$env:APPDATA\Anki2\addons21\178037783" `
    -Target "$pwd\addon"
```

## Code standards

- Keep modules import-safe outside Anki (no `aqt.qt` imports at
  module level in `utils`, `search`, `logger`, `yimages`, `gimages`,
  `ddg_hidden_test`).
- One widget per file under `tabs/`; the dialog in `ui_menu.py` is a
  thin shell that wires the tabs together.
- Always log user-visible actions (`log.info` / `log.warning`) and
  pass `exc_info=True` on error paths.
- Run `python3 -m unittest discover -s tests` before committing.
