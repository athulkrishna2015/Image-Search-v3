# Module-level State

A consolidated view of everything that lives in memory at runtime
and is not part of the Anki collection. The principle is: **keep
state local to the editor window when possible, share when there
is only one logical instance.**

## `addon/logger.py`

| Name | Type | Scope | Lifetime | Notes |
| --- | --- | --- | --- | --- |
| `LOG_DIR` | `str` | process | constant | `<addon>/logs/` (excluded from .ankiaddon, gitignored). |
| `LOG_FILE` | `str` | process | constant | `<addon>/logs/image_search_v3.log`. |
| `LOGGER_NAME` | `str` | process | constant | `"image_search_v3"`. |
| `_DEFAULT_MAX_BYTES` | `int` | process | constant | 512 KiB. |
| `_DEFAULT_BACKUP_COUNT` | `int` | process | constant | 3 (`image_search_v3.log.1` / `.2` / `.3`). |
| `_AddonLogger._logger` | `logging.Logger` | process | add-on import | stdlib logger; lazily attaches a `RotatingFileHandler` on first call. |
| `_AddonLogger._handler` | `RotatingFileHandler` or `None` | process | until add-on reload | Attached on first call. |
| `_AddonLogger._current_level_name` | `str` | process | until add-on reload | Mirrors the in-memory level; updated by `set_level`. |

## `addon/utils.py`

| Name | Type | Scope | Lifetime | Notes |
| --- | --- | --- | --- | --- |
| `CURRENT_DIR` | `str` | process | add-on import | Derived from `__file__`. |
| `_NET_CHECK_HOSTS` | `tuple[str, …]` | process | constant | DNS probe hosts. |
| `_NET_CHECK_TIMEOUT_S` | `float` | process | constant | Probe timeout. |
| `_UA` | `str` | process | constant | Default User-Agent. |
| `_DEFAULT_REFERER` | `str` | process | constant | Default `Referer` header. |
| `_ACCEPT_IMG` | `str` | process | constant | Default `Accept` header. |
| `_WARNED_KEYS` | `set[tuple]` | process | add-on import | Throttles repeated `report` modals. Cleared on add-on reload. |
| `_NET_DEFAULTS` | `dict` | process | constant | Default network settings. |

## `addon/search.py`

| Name | Type | Scope | Lifetime | Notes |
| --- | --- | --- | --- | --- |
| `RESULTS` | `dict[str, list[str]]` | process | until add-on reload | Cached URL lists per query. |
| `INDICES` | `dict[str, int]` | process | until add-on reload | Current index per query (`-1` if empty). |
| `PROVIDERS` | `dict[str, str]` | process | until add-on reload | Human label per query for the tooltip. |
| `MAX_CACHED_QUERIES` | `int` | process | constant | LRU cap, default `100`. |

The cache is bounded by `_evict_cache_if_needed`, which removes the
oldest entry (insertion order = LRU) every time a new entry is
added. `_touch_query` is called on `getresultbyquery`,
`getnextresultbyquery`, and `getprevresultbyquery` so any activity
counts as recency.

## `addon/ui_editor.py`

| Name | Type | Scope | Lifetime | Notes |
| --- | --- | --- | --- | --- |
| `_HOOKS_INSTALLED` | `bool` | process | until add-on reload | Idempotency guard. |
| `_MW_HOOK_FLAG` | `str` | process | constant | Attribute name on `mw` to survive a process restart within a single Anki session. |
| `editor._imgsearchv3_last_query` | `str` | per editor | until the editor is closed | Replaces the previous module-level `last_query` so multiple editor windows do not interfere. |

## `addon/ui_menu.py`

| Name | Type | Scope | Lifetime | Notes |
| --- | --- | --- | --- | --- |
| `_MENU_INSTALLED` | `bool` | process | until add-on reload | Idempotency guard. |
| `_MW_MENU_FLAG` | `str` | process | constant | Attribute name on `mw`. |

## `addon/yimages.py`, `gimages.py`, `ddg_hidden_test.py`

Only constants (`BASE_URL`, `_HEADERS`, …). No mutable state.

## What is **not** stored in memory

- The selected image — it is downloaded to a temp file and immediately
  added to Anki media via `addFile`. The temp file is deleted in the
  same call. The only persistent artifact is the media file inside
  the Anki collection.
- The `editor.note.fields[…]` text — managed by Anki; we only mutate
  it via `editor.note.fields[i] = …` or via the smart-replace path.
