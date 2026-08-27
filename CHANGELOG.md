# Changelog

All notable changes to **Image Search v3** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/) in the form
`3.<major>.<minor>` (the leading `3` is fixed and matches the Anki add-on's
public package id `178037783`).

Releases on GitHub: <https://github.com/athulkrishna2015/Image-Search-v3/releases>

---

## [Unreleased]

### Changed
- Network image downloads now share the same retry/backoff settings as the
  search providers (previously a single transient failure aborted the
  download with no retry).
- Per-note-type warning dialogs are throttled so a misconfigured note type no
  longer spams the user on every search.
- The provider dropdown now uses only its `objectName` for duplicate
  detection (Anki menu language no longer affects re-install detection).

### Fixed
- `editor.loadNote()` is no longer called on smart-replace, preserving the
  editor's cursor position, focus, and undo stack.
- The `last_query` cache is now stored on the editor instance instead of a
  module-level global, so multiple editor windows do not interfere with
  each other's previous/next navigation.
- `next`/`prev` now refresh LRU recency so the query you are browsing does
  not get evicted from the in-memory cache.
- `mkstemp` filename prefixes are sanitized, preventing `ValueError` from
  reaching the user when a provider returns a URL with unexpected characters.
- `media.addFile` is called with `force_copy=True` when the running Anki
  supports it, so the downloaded temp file is always safe to delete
  afterwards.
- `image_tag` HTML-escapes the `src` value.
- A global `query_fields: ["Front"]` default that fired a modal on every
  search for non-Cloze note types has been removed from `config.json` and
  `manifest.json`.
- Yandex response parser now accepts both `data-bem='{...}'` (single quotes)
  and `data-bem="{...}"` (double quotes), and resolves protocol-relative
  thumbnail URLs (`//avatars.example/...`).

### Security
- `addon/meta.json` (auto-managed by Anki, can contain user credentials)
  was already in `.gitignore`; verified it is not in any branch's history.
  The Google API key rotation policy is documented in `doc/SECURITY.md`.

### Tests
- Added `tests/test_utils.py` (15 new tests) covering URL extension
  inference, image tag escaping, prefix sanitization, smart-replace
  behavior, and the LRU-on-nav semantics.

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

[Unreleased]: https://github.com/athulkrishna2015/Image-Search-v3/compare/v3.11.2...HEAD
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
