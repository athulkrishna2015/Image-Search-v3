# Testing

## Run the suite

```bash
cd /path/to/Image-Search-v3
python3 -m unittest discover -s tests -v
```

Expected: **23 tests, all passing**.

## Layout

```
tests/
├── test_search.py            ← provider routing, fallback, LRU cache, nav
├── test_utils.py             ← suffix inference, image_tag, prefix sanitization,
│                                smart-replace, LRU touch-on-nav
├── test_logger.py            ← logger: level set/filter, file creation, clear,
│                                tail truncation, missing file
├── test_log_all_and_supporter.py
│                             ← logger 'all' level, below-DEBUG capture,
│                                tail_text UnboundLocalError regression,
│                                supporter opt-out defensive write
├── test_log_check_and_clear.py
│                             ← log scanner (Traceback, Timeout, provider
│                                give-up, settings save failure), sample
│                                truncation, clear-on-startup default/off/
│                                enabled/missing-file, non-modal dialog
│                                AST inspection
├── test_yandex_fix_and_bing.py
│                             ← Yandex parser regression (drill into
│                                serp-item), Bing provider extractor
│                                (murl, dedup, retry), search routing for
│                                provider=bing (primary + fallback)
├── test_bump_and_update.py   ← bump.py: validate / increment / sync / read /
                                 bump_version; update_check: should_show /
                                 mark_welcomed, opt-out, disabled, no-startup-
                                 side-effects (AST inspection)
```

Both files live in a regular directory (no `__init__.py`). Discovery
uses `unittest`'s default file pattern (`test_*.py`).

## Stubs used by the tests

The test files build their own `aqt`, `anki`, and per-module stubs
at runtime so they do not need a real Anki install. The pattern
(used in `test_search.py` and `test_utils.py`):

```python
import types, sys
aqt = types.ModuleType("aqt")
aqt.mw = types.SimpleNamespace(addonManager=types.SimpleNamespace(getConfig=lambda _: {}))
sys.modules["aqt"] = aqt
```

After the stubs are in place, the modules under `addon/` are
imported with `importlib.util.spec_from_file_location` so we do not
trigger `addon/__init__.py`.

## What's covered

| Area | Test file | Notes |
| --- | --- | --- |
| `search._provider_results_and_label` (routing) | `test_search` | DDG primary, DDG→Yandex fallback, Google→Yandex fallback, Google no-fallback, default Yandex. |
| `search._clean_query` | `test_search` | HTML stripping via a stubbed `strip_html_media`. |
| `search.getresultbyquery` / next / prev | `test_search` | End-to-end navigation; clamping at the ends. |
| LRU eviction (oldest gone) | `test_search` | `MAX_CACHED_QUERIES = 2`, three queries. |
| LRU touch on next/prev | `test_utils` | New: navigating must refresh recency. |
| `utils._infer_suffix_from_url` | `test_utils` | Common extensions (case-insensitive), unknown defaults to `.jpg`, garbage inputs. |
| `utils.image_tag` | `test_utils` | Output shape, attribute escaping, `None` input. |
| `utils._safe_prefix` | `test_utils` | Default fallback, path separator stripping, safe-char preservation, length cap. |
| `ui_editor._replace_last_imgsearch_tag` | `test_utils` | Replaces only the last matching tag, returns `None` on no match, leaves non-imgsearch images alone. |

## What's **not** covered (and worth adding)

- `ui_menu.SettingsDialog` — would need `pytest-qt` or a manual
  Anki harness. Skipped because of maintenance burden.
- `yimages.parse_yimages_response` — the markup drifts; tests would
  need to be updated each time Yandex changes. The current fix
  (accept both `'` and `"`) is verified by inspection.
- `utils.save_file_to_library` end-to-end — needs a fake
  `editor.mw.col.media` and a fake `_download_bytes`. Worth adding
  if the download path changes again.
- Integration test with a real Anki collection. Out of scope here.

## Adding a test

1. Pick the right file (`test_search.py` for `search.py`,
   `test_utils.py` for everything else).
2. Follow the existing stub pattern; do not import Anki.
3. Keep the assertion message small; the test name is the
   documentation.
4. Run the suite before committing.
