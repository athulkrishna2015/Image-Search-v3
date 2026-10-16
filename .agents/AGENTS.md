# AGENTS.md

Guidance for AI coding assistants and contributors working on the
**Image Search v3** Anki add-on.

## Project Layout

```
addon/                       # The actual add-on payload (zipped into .ankiaddon)
  __init__.py                # Add-on entry point; GUI import + hook bootstrap
  ui_editor.py               # Editor toolbar/context menu: search, prev, next, paste
  ui_menu.py                 # Tools menu entry for the settings dialog
  search.py                  # Provider routing, fallback chain, per-query result cache
  utils.py                   # Field resolution, media download/save, HTML <img> tag
  logger.py                  # Rotating file handler, level filtering, log helpers
  update_check.py            # Add-on version / update welcome
  yimages.py bing_images.py gimages.py ddg_hidden_test.py brave_images.py
  yandex_official.py         # Image providers (one module per provider)
  tabs/                      # Settings dialog tabs (note types, network, logs, support)
  Support/                   # Support tab assets
  config.json                # Shipped defaults (committed, never contains secrets)
  manifest.json VERSION      # Package metadata and version
doc/                         # Developer documentation (markdown)
  ARCHITECTURE.md BUILD.md CONFIG.md ERRORS.md MODULES.md PROVIDERS.md
  SECURITY.md STATE.md TESTING.md
tests/                       # pytest-based regression tests
make_ankiaddon.py            # Build script: bumps VERSION, packages addon/ -> .ankiaddon
bump.py                      # Version bump helper (used by make_ankiaddon.py)
CHANGELOG.md                 # Release history (add an entry per release)
.github/workflows/release.yml  # Release pipeline: test -> build -> attach -> AnkiWeb upload
```

## Runtime notes

- `addon/meta.json` is Anki-managed runtime config and is **gitignored**. It may
  contain API keys (Google CSE, Brave token, Yandex). Never commit or echo it.
- Config defaults live in the committed `addon/config.json`; Anki merges them on
  first install, then `meta.json` overrides them. Settings writes must go through
  Anki's config API, never a raw file write.
- Per-note-type settings live under `configs_by_notetype_id` keyed by the note
  type id **as a string**. `image_placement` is one of `replace` / `append` /
  `prepend` and defaults to `replace`.
- Images added by the add-on are tagged `class="imgsearch"`. That class is the
  only thing smart replace is allowed to match — never rewrite or drop other
  `<img>` tags, since users hand-write those.
- Logs go to `addon/logs/image_search_v3.log` (gitignored, excluded from the
  package) with three rotations.

## Conventions

- **No comments unless asked.** Keep the code comment-light, matching the
  surrounding style.
- **Providers are lazily imported** in `search.py` via the `_PROVIDER_LOADERS`
  table, so one broken provider must never stop the add-on from loading. A
  failing loader logs a warning and contributes no results instead of raising.
- **Fallback chain semantics:** the selected provider is always tried first; the
  configured `fallback_providers` list is the chain *after* it. An explicit empty
  list disables fallback.
- **Never write to the note outside `ui_editor.display_image`.** It is the single
  place that decides placement, and it must keep the in-place swap free of
  `loadNote()` so editor focus, undo history, and the selection survive.

## Testing

```
python3 -m pytest tests/ -q --ignore=tests/test_yandex_official.py
python3 -m pytest tests/test_yandex_official.py -q
```

Two interpreters, and **not** one per file, because the suites share global
`anki`/`aqt` stubs and pollute each other in both directions:

- `test_yandex_official` installs an `addon.utils` stub that breaks its
  neighbours, so it must run alone.
- `test_utils` only imports cleanly once a sibling suite has put the `anki`/`aqt`
  stubs into `sys.modules`, so it must **not** run alone.

A combined run of everything (or running either file by itself) fails for those
reasons, not because of a real regression — don't "fix" it by editing tests.
`test_yandex_official` hits the live network and takes ~25s.

Runners have no Anki install, so CI installs `pytest` and `requests` only (the
suites mock `aqt`/`anki` themselves). A local machine with Anki installed hides
this pollution — reproduce CI in a bare venv when a test behaves differently
locally.

## Release flow

Releases are automated. Publishing a GitHub release fires
`.github/workflows/release.yml`, which runs the tests, rebuilds the
`.ankiaddon` **from the tag**, attaches it to the release, and uploads it to
AnkiWeb. Do not attach an asset yourself — CI builds and attaches it.

1. Make changes; commit on `main` (this repo does not use branches for releases).
2. Bump + build locally to sanity-check:
   ```
   python3 make_ankiaddon.py            # auto-bumps the patch version
   python3 make_ankiaddon.py 3.12.3     # or force an explicit version
   ```
   This updates `addon/VERSION` + `addon/manifest.json` and writes
   `Image_Search_v3_v<version>_<timestamp>.ankiaddon` in the repo root
   (gitignored). CI forces the tag's version anyway; these two files just track
   the last release.
3. Add a `## [x.y.z] — YYYY-MM-DD` entry to `CHANGELOG.md`, and add the matching
   link reference at the bottom of the file.
4. Commit: `release: Image Search v3 x.y.z`.
5. Tag **the exact release commit** and push:
   ```
   git tag -a vX.Y.Z -m "Image Search v3 vX.Y.Z"
   git push origin main
   git push origin vX.Y.Z
   ```
6. Draft the release, check it on the GitHub page, then publish — still with
   **no asset argument**:
   ```
   gh release create vX.Y.Z --title "Image Search v3 vX.Y.Z" --notes "<release notes>" --draft
   gh release edit vX.Y.Z --draft=false
   ```
   Drafting runs nothing; `--draft=false` is the "go" that fires the workflow. Do
   not collapse this into one publish command — the draft is the only gate
   between a mistyped tag and an irreversible public AnkiWeb upload. If CI fails
   after publishing, the release sits published but asset-less (AnkiWeb
   untouched); fix it and re-run from Actions → Release → Run workflow.

A `release: published` event runs the workflow file **from the tag**, so every CI
change must be committed *before* tagging — one committed afterwards never
reaches that path. If you still need a CI fix afterwards, move the tag
(`git tag -f -a vX.Y.Z <commit> && git push origin vX.Y.Z --force`); `.github/`
is never packaged, so the shipped bytes do not change.

Rehearse or re-run from Actions → Release → Run workflow:

| `tag` | `dry_run` | Result |
| --- | --- | --- |
| existing release tag | off | rebuild, re-attach, re-upload to AnkiWeb |
| existing release tag | on | tests + build only; nothing published |
| branch (e.g. `main`) | on | rehearsal built from the branch |
| branch | off | refused — nothing is ever published off an untagged commit |

Release invariants:

- **`README.md` must stay under 65,535 bytes** — it *is* the AnkiWeb listing
  description. AnkiWeb rejects an over-limit description and the listing then
  silently keeps its previous text, so CI fails the build up front instead.
- **One-time secrets:** `ANKIWEB_USERNAME` / `ANKIWEB_PASSWORD` in repo Settings
  → Secrets and variables → Actions. Never commit or echo them. The local source
  of truth lives in the `ankiweb-api` sibling repo's gitignored `.env`.
- The listing (AnkiWeb addon `178037783`, "Image Search v3", branch `2.1.1+`) has
  its title, tags and support page re-sent on every upload — change those in the
  workflow, not by hand.
- Uploads go through
  [`athulkrishna2015/ankiweb-api`](https://github.com/athulkrishna2015/ankiweb-api).
  Verify afterwards with that repo's `ankicli.py info 178037783`, and for a
  byte-level check compare `sha256sum` of the downloaded listing file against the
  GitHub release asset — the hashes must match. Two traps make a good upload look
  lost: `item-info` is cached for 10 minutes without its `cb` cache-buster, and a
  plain `curl` of `ankiweb.net/shared/info/...` returns only a SvelteKit JS shell
  (use `ankicli.py`, not curl).

## Common edit pitfalls

- **Only one image lands on a card** → in *Replace* placement a *new* query must
  append (see `display_image(..., is_new_search=True)`); only same-query browsing
  swaps. Passing the old default silently reverts to overwrite-on-every-search.
- **`get_note_image_field_index` falls back to the last field** and warns once per
  note type when the configured field is missing. A "wrong field" bug is usually
  a config lookup bug, not a fallback bug.
- **A provider returns 0 results** → check the fallback chain log line
  (`provider routing: primary=... chain=[...]`) before suspecting the parser.
  Each provider module logs its own request/result counts.
- **Images 404 after paste** → the file must be added to the media collection via
  `editor.mw.col.media.addFile`, never copied into the collection folder by hand;
  the bundled package excludes `meta.json` and logs on purpose.

## When you are stuck

- Logs: ask the user to paste `addon/logs/image_search_v3.log` (plus the `.1`/`.2`/`.3`
  rotations if relevant). The Logs tab can also run a health scan for known error
  patterns.
- Config: `addon/meta.json`, falling back to the committed `addon/config.json` for
  the shipped defaults.
- Code questions: search the repo first (`rg`); `doc/` holds architecture,
  module, config-key, error, and testing references.