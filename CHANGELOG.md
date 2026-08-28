# Changelog

All notable changes to **Image Search v3** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/) in the form
`3.<major>.<minor>` (the leading `3` is fixed and matches the Anki add-on's
public package id `178037783`).

Releases on GitHub: <https://github.com/athulkrishna2015/Image-Search-v3/releases>

---

## [3.12.2] — 2026-08-28

### Latest changes (summary)

- **3.12.2 (2026-08-28)** — fallback providers can now be reordered by
  dragging them in the Network tab, and the Network / Note Types / Logs
  controls now have hover tooltips for their settings.

### Added
- Drag-and-drop fallback priority ordering in the Network tab.
- Hover tooltips across the main settings controls so each option
  explains itself on mouse hover.

### Changed
- The fallback provider list now preserves the saved drag order and
  skips unchecked providers when building the chain.

### Changed
- Global fallback routing now tries any configured provider after any
  other provider returns no results or errors, instead of only
  falling back to Yandex for specific providers.
- Update-check metadata persistence now works in both standard Anki
  installs and development symlink checkouts.
- Packaging and release documentation updated for the 3.12.0 release.

---

## [Unreleased]

### Added
- **Bing provider (keyless)** via the undocumented `/images/async`
  endpoint. No API key required; returns ~30–50 results per query by
  extracting `murl` values from the response HTML. Selectable as
  `provider = "bing"` in the Network tab; falls back to Yandex on
  empty results.
- **Brave Image Search API provider** via the documented
  `/res/v1/images/search` endpoint. Requires a Brave Search
  subscription token (configurable in the Network tab as
  `brave_api_key`). Returns up to 200 results per request by
  preferring the `properties.url` (original) field, falling back to
  `thumbnail.src` (Brave-proxied). Selectable as `provider = "brave"`.
  Falls back to Yandex on empty results.
- Logs tab "live update" toggle: the text area auto-refreshes
  whenever the log file's mtime changes (1.5s poll). Disabling the
  toggle stops the poll and keeps the view static. New content is
  appended without overwriting the user's current view; "Clear log"
  forces a full reload.
- Logs tab restructured so all controls (path, log level, debug
  toggle, maintenance checkboxes, all action buttons, live-update
  toggle, findings label, help) are at the top; the text area is at
  the bottom and takes the remaining space.
- `clear_logs_on_startup` config key (default `true`). When enabled,
  the add-on truncates the log file on every Anki session start.
  Wired in `addon/__init__.setup()`.
- `auto_show_support_on_update` config key (default `true`). When
  the add-on version changes, the Support tab is auto-focused the
  next time the user opens the settings dialog (lazy, no Anki
  startup cost). Disabled by ticking **"I have supported this
  addon"** in the Support tab, which is stored in `meta.json`.

### Changed
- Settings dialog is now **non-modal**: opening it does not block
  the Anki main window. A single live instance is kept so re-opening
  the menu re-focuses the existing window instead of stacking a new
  one. `WA_DeleteOnClose` + `closeEvent` wired to the cancel handler
  so the X button discards unsaved per-note-type changes.
- Logs tab "Live update" enabled by default.

### Fixed
- **Yandex parser** was looking for `thumb.url` on the outer
  `data-bem` object (`{"serp-item":{...}}`) but the snippet wraps
  the actual fields inside the nested `serp-item` object. Fixed
  to drill into `serp-item` first, with a flat-object fallback for
  older payloads. Restores all 30 image URLs per query (was 0).
- **DuckDuckGo User-Agent** updated from `Windows NT 10.0` Chrome
  to `X11; Linux x86_64` Chrome. DDG has been observed to return
  403 for the Windows UA on the hidden `i.js` endpoint; the Linux
  UA is accepted across the network. (Yandex and Bing headers
  updated to the same Linux UA for consistency.)
- The Logs tab "Clear log" button no longer leaves a stale
  view: it now resets the cached file size and re-renders from
  scratch.
- Yandex parser accepts both `data-bem='{...}'` (single quotes) and
  `data-bem="{...}"` (double quotes), and resolves protocol-relative
  thumbnail URLs (`//avatars.example/...`).

### Security
- `addon/meta.json` (auto-managed by Anki, can contain user
  credentials) was already in `.gitignore`; verified it is not in
  any branch's history.

### Tests
- Added `tests/test_utils.py` (15 tests) covering URL extension
  inference, image tag escaping, prefix sanitization, smart-replace
  behavior, and the LRU-on-nav semantics.
- Added `tests/test_logger.py` (9 tests) covering logger levels,
  filtering, file creation, clear, tail truncation, missing file.
- Added `tests/test_log_all_and_supporter.py` (8 tests) covering
  the `all` level (lowest), UnboundLocalError regression in
  `tail_text`, and defensive write of supporter opt-out.
- Added `tests/test_log_check_and_clear.py` (13 tests) covering
  the log health scanner and the non-modal-dialog AST inspection.
- Added `tests/test_bump_and_update.py` (16 tests) for the build
  script and the update-check helpers.
- Added `tests/test_yandex_fix_and_bing.py` (12 tests) for the
  Yandex parser regression, the Bing provider extractor, and the
  Bing search-routing primary + fallback paths.
- Added `tests/test_brave.py` (12 tests) for the Brave provider
  parser (extracts `properties.url`, falls back to `thumbnail.src`,
  never uses the top-level `url` which is the page URL), the
  request shape (`X-Subscription-Token`, `count`, `safesearch`),
  the missing-key short-circuit, the 4xx error path, the
  retry-on-timeout loop, and the max-retries exit condition.
- Added 3 routing tests for `provider = "brave"` (primary,
  fallback to Yandex, no-fallback) in `tests/test_yandex_fix_and_bing.py`.

---

## [3.11.2] — 2026-03-27

### Added
- Ko-fi support widget (third-party JS embed) on the settings dialog's
  Support tab.
- "Support" tab in the settings dialog with QR codes and copy buttons for
  UPI, BTC, and ETH addresses.

---

## [3.11.0] — 2026-03-17

### Added
- DuckDuckGo (hidden API) provider option alongside Yandex (default) and
  Google.
- Toolbar buttons now use emoji labels (🖼 ⬅ ➡) since image assets were
  removed.
- Build/version scripts now enforce the `3.<major>.<minor>` scheme with a
  fixed leading `3`.
- `addon/VERSION` file is written by `make_ankiaddon.py` and `bump.py`.
- `tests/test_search.py` covering provider routing, fallback, cache, and
  next/prev behavior.

---

## [3.10.0] — 2026-03-09

- Internal release. No public changelog published.

---

## [3.9.0] — 2026-02-24

### Security
- Removed insecure TLS behavior in Yandex requests (no disabled certificate
  verification/warnings suppression).

### Reliability
- Hardened network config parsing (timeout/retries/backoff) with safe
  fallbacks and value bounds to avoid crashes from malformed config values.
- Fixed temporary file cleanup to ensure downloaded temp files are deleted
  even when download/media import fails.
- Network availability check now restores the previous global socket
  timeout instead of mutating process-wide defaults.

### UX / Data safety
- Fixed settings dialog dirty-state handling so switching note types does
  not silently discard unsaved Network tab changes.
- Made editor hook and Tools menu registration idempotent to prevent
  duplicate toolbar/context-menu/menu entries on add-on reloads.

### Performance
- Added a bounded in-memory query cache (LRU-style eviction) to prevent
  unbounded growth during long sessions.

---

## [3.8.6] — 2025-11-04

### Added
- Google provider using Custom Search JSON API with images. Users enter
  their Google API key and CSE ID (`cx`) in settings and select Google as
  provider, with automatic fallback to Yandex if Google returns no items.
- Settings now include provider selection plus request timeout, max
  retries, and exponential backoff base, grouped under the Network tab.
- Image saving infers file extensions from URLs
  (`jpg`/`jpeg`/`png`/`gif`/`webp`/`bmp`) instead of forcing a single
  format to improve media compatibility across providers.
- Network availability check tries multiple hosts to reduce false offline
  errors in restrictive networks or partial outages.
- Settings dialog initialization hardened so status messages work reliably
  even if signals fire early during widget setup.

---

## [3.8.3] — 2025-11-04

- Internal packaging release.

---

## [3.7.4] — 2025-11-02

- Internal packaging release.

---

## [3.7.3] — 2025-11-01

### Fixed
- Yandex parser edge cases around `data-bem` extraction.

---

## [3.7.1] — 2025-11-01

- Documentation and packaging updates.

---

## [3.6.4] — 2025-11-01

### Fixed
- Better error message when no image results are returned.

---

## [3.6.3-public] — 2025-10-31 (GitHub tag `tag`)

### Added
- Smart Replace: only replaces images inserted by this add-on (identified
  by `class="imgsearch"`) and never overwrites existing text or manually
  pasted images; if no prior add-on image exists, it appends instead.
- Default placement is "replace" in code and settings but remains
  non-destructive: original field content is preserved and only prior
  add-on images are swapped.
- Right-click context menu registered using
  `gui_hooks.editor_will_show_context_menu` with a legacy fallback for
  older builds, so "Search image for selection" appears reliably.
- Yandex request pipeline hardened: explicit timeouts, limited retries
  with backoff, and robust JSON checks to avoid `KeyError`/`TypeError` on
  slow or offline networks.
- Media downloads are offline-aware: quick DNS check, structured error
  codes (`offline` / `network` / `unexpected`), and a single concise
  user message instead of duplicate popups.
- Per-note-type settings dialog: Save no longer closes the dialog;
  defaults initialize placement to "replace", first field for queries,
  and last field for images.
- Safer field resolution: if a configured image field is missing, the
  add-on falls back to the last field and warns; query field selection
  falls back to the first field.
- Default config simplified: global `image_field` removed; `query_fields`
  defaults to `["Front"]` for cleaner per-note-type configuration.

---

## [3.6.2-public] — 2025-10-31 (GitHub tag `release`)

- Initial public release of v3 (fork of Anki Image Search v2 and Image
  Search). Pre-notetype-config build with single Yandex provider.

---

[Unreleased]: https://github.com/athulkrishna2015/Image-Search-v3/compare/v3.12.2...HEAD
[3.12.2]: https://github.com/athulkrishna2015/Image-Search-v3/releases/tag/v3.12.2
[3.12.1]: https://github.com/athulkrishna2015/Image-Search-v3/releases/tag/v3.12.1
[3.12.1]: https://github.com/athulkrishna2015/Image-Search-v3/releases/tag/v3.12.1
[3.12.0]: https://github.com/athulkrishna2015/Image-Search-v3/releases/tag/v3.12.0
[3.11.2]: https://github.com/athulkrishna2015/Image-Search-v3/releases/tag/v3.11.2
[3.11.0]: https://github.com/athulkrishna2015/Image-Search-v3/releases/tag/v3.11.0
[3.10.0]: https://github.com/athulkrishna2015/Image-Search-v3/releases/tag/v3.10.0
[3.9.0]: https://github.com/athulkrishna2015/Image-Search-v3/releases/tag/v3.9.0
[3.8.6]: https://github.com/athulkrishna2015/Image-Search-v3/releases/tag/3.8.6
[3.8.3]: https://github.com/athulkrishna2015/Image-Search-v3/releases/tag/3.8.3
[3.7.4]: https://github.com/athulkrishna2015/Image-Search-v3/releases/tag/3.7.4
[3.7.3]: https://github.com/athulkrishna2015/Image-Search-v3/releases/tag/3.7.3
[3.7.1]: https://github.com/athulkrishna2015/Image-Search-v3/releases/tag/3.7.1
[3.6.4]: https://github.com/athulkrishna2015/Image-Search-v3/releases/tag/3.6.4
[3.6.3-public]: https://github.com/athulkrishna2015/Image-Search-v3/releases/tag/tag
[3.6.2-public]: https://github.com/athulkrishna2015/Image-Search-v3/releases/tag/release
