# Module Reference

Every Python file under `addon/`, what it owns, and what it exports.

## `addon/__init__.py`

Entry point. Defines `setup()` and runs it on import. Imports
`ui_editor` and `ui_menu` lazily inside `setup()` to avoid
circular-import issues during Anki's add-on reload cycle.

## `addon/logger.py`

Rotating file logger. The handler is attached lazily on first use so
importing the add-on outside Anki (tests, build scripts) never
touches the filesystem.

| Symbol | Purpose |
| --- | --- |
| `LOG_DIR` | `addon/logs/` (excluded from the .ankiaddon). |
| `LOG_FILE` | `addon/logs/image_search_v3.log`. |
| `LOGGER_NAME` | `"image_search_v3"`. |
| `_AddonLogger` | Thin wrapper around `logging.getLogger(...)` with `set_level` / `tail_text` / `clear`. |
| `log` | Singleton instance used by all modules. |
| `log.debug / info / warning / error / exception / critical` | Stdlib-style API. `error(..., exc_info=True)` includes the current traceback. |
| `log.set_level(name)` | One of `debug` / `info` / `warning` / `error` / `critical`. Silently ignored for unknown values. |
| `log.get_level()` | Current level name. |
| `log.tail_text(max_bytes=64 KiB)` | Last bytes of the current log for the Logs tab. |
| `log.clear()` | Truncate current file and remove `.1`/`.2`/`.3` backups. |
| `log.log_path()` / `log.log_dir()` | Absolute paths used by the Logs tab. |

## `addon/utils.py`

Shared helpers. **No Qt imports at module scope** so the file is
import-safe from tests/build scripts.

| Symbol | Purpose |
| --- | --- |
| `CURRENT_DIR` | Absolute path of the add-on directory. |
| `_NET_CHECK_HOSTS`, `_NET_CHECK_TIMEOUT_S` | Hosts tried by the offline probe. |
| `_UA`, `_DEFAULT_REFERER`, `_ACCEPT_IMG` | Default HTTP headers for image downloads. |
| `_WARNED_KEYS` | Set of `(category, …)` tuples used to throttle warning modals. |
| `_NET_DEFAULTS` | Default `request_timeout_s`/`max_retries`/`backoff_base_s`. |
| `safe_float(value, default, minimum=None, maximum=None)` | Tolerant float parser with optional clamping. |
| `safe_int(value, default, minimum=None, maximum=None)` | Same, for ints. |
| `get_net_settings()` | Returns `(timeout_s, max_retries, backoff_base_s)` from `addonManager.getConfig`, clamped. |
| `path_to(*args)` | Joins a path under the add-on directory. |
| `get_config()` | Wraps `mw.addonManager.getConfig(__name__)`. |
| `report(text, *, key=None, title="Image Search v3")` | Show a modal warning. Pass `key` to dedupe per session. |
| `notify(text, period_ms=2500)` | Non-blocking tooltip; falls back to `showInfo` only if tooltip is unavailable. |
| `get_note_query(note)` | Resolve the search query for a note (per-notetype, then global, then heuristic). |
| `get_note_image_field_index(note)` | Resolve the field index to receive the image. |
| `_network_available()` | Cheap DNS probe across `_NET_CHECK_HOSTS`. |
| `_infer_suffix_from_url(url)` | `.jpg`/`.png`/`.gif`/`.webp`/`.bmp` or `.jpg` if unknown. |
| `_download_bytes(url, timeout_s, max_retries, backoff_base_s)` | `urllib`-based GET with browser headers, retries with backoff. |
| `_safe_prefix(raw, default="img_", max_len=32)` | Sanitize a string into a `mkstemp`‑safe prefix. |
| `save_file_to_library(editor, image_url, prefix, suffix)` | Download to a temp file and import to Anki media. Returns `(filename, error_code)`. |
| `_add_file_safely(editor, temp_path)` | Wrapper around `media.addFile` that prefers `force_copy=True`. |
| `save_image_to_library(editor, image_url)` | Derive a stable prefix from `id=…` in the URL, infer suffix, call `save_file_to_library`. |
| `image_tag(image_src)` | Returns `<img src="…" class="imgsearch">` (HTML-escaped). |

### Error codes returned by `save_file_to_library` / `save_image_to_library`

| Code | Meaning |
| --- | --- |
| `None` | Success; the tuple's first element is the media filename. |
| `"offline"` | The DNS probe failed for all configured hosts. |
| `"network"` | `URLError`, `HTTPError`, or `socket.timeout` after all retries. |
| `"unexpected"` | Any other exception (e.g. disk full). The user sees a modal with the traceback. |

## `addon/search.py`

In-memory LRU cache of search results, plus the routing logic that
picks Yandex / DuckDuckGo / Google based on the user config.

| Symbol | Purpose |
| --- | --- |
| `RESULTS` | `dict[query, list[str]]` of cached image URLs. |
| `INDICES` | `dict[query, int]` cursor per query. `-1` means "no results". |
| `PROVIDERS` | `dict[query, str]` human label per query (used by the tooltip). |
| `MAX_CACHED_QUERIES` | LRU cap (default `100`). |
| `_clean_query(q)` | Strips HTML media tags via `anki.utils.strip_html_media`. |
| `_provider_label_from_config()` | Map current config → label without consulting the cache. |
| `_current_url(q)` | URL at the current index, or `None`. |
| `_touch_query(q)` | Re-insert `q` at the end of each cache dict (LRU recency). |
| `_evict_cache_if_needed()` | Drop the oldest entries until size ≤ `MAX_CACHED_QUERIES`. |
| `_provider_results_and_label(q)` | Returns `(urls, label)` per current provider config, including fallback. |
| `get_provider_label(q)` | Label for `q` (cached → configured). |
| `getresultbyquery(q)` | Cached list for `q`; runs the provider if not cached; touches & evicts. |
| `getnextresultbyquery(q)` | Advance the cursor; touch the cache; return current URL. |
| `getprevresultbyquery(q)` | Step the cursor back; touch the cache; return current URL. |

## `addon/yimages.py`

Yandex "infinite scroll" JSON endpoint. **Undocumented public
endpoint; may break without notice.**

| Symbol | Purpose |
| --- | --- |
| `BASE_URL` | URL template; `text=` is appended (URL-encoded). |
| `headers` | Static `User-Agent`. |
| `make_yimages_url(q)` | URL-encode and append the query. |
| `get_yimages_response(q)` | `requests.get` with retries via `get_net_settings()`. Returns parsed JSON or `None`. |
| `parse_yimages_response(response)` | Walk `response.blocks[0].html`, extract `data-bem='{…serp-item…}'` (or `="…"`), parse each JSON, return `["https:" + thumb.url]`. |
| `get_yimages(q)` | `parse_yimages_response(get_yimages_response(q))`. |
| `getyimages` | Backwards-compatible alias of `get_yimages`. |

## `addon/gimages.py`

Google Custom Search JSON API (searchType=image). Requires user
credentials.

| Symbol | Purpose |
| --- | --- |
| `_get_google_creds()` | Returns `(api_key, cx)` from the add-on config (or `("", "")`). |
| `getgimages(q)` | `requests.get("https://www.googleapis.com/customsearch/v1", params=…)` with `num=10` (the per-request hard limit). Returns `[item.link]`. |

## `addon/ddg_hidden_test.py`

DuckDuckGo via the hidden `i.js` endpoint. **Undocumented, may break.**

| Symbol | Purpose |
| --- | --- |
| `_DDG_SEARCH_URL`, `_DDG_IMAGE_API_URL` | Endpoints. |
| `_HEADERS` | Browser-like headers (incl. `Referer` and `Origin`). |
| `_request_with_retry(url, params, …)` | GET with timeout + exponential backoff. |
| `_get_vqd(q, …)` | Extract the CSRF-like `vqd` token from the HTML of the search page. |
| `get_ddg_images(q)` | Two-step: fetch `vqd`, then hit `i.js`, return `result[].image`. |
| `getddgimages` | Backwards-compatible alias. |

## `addon/ui_editor.py`

All editor-side UI: toolbar buttons, context menu, the
`on_search` / `on_next` / `on_previous` callbacks, and
`display_image`.

| Symbol | Purpose |
| --- | --- |
| `_HOOKS_INSTALLED`, `_MW_HOOK_FLAG` | Idempotency guards (avoids duplicate buttons on add-on reload). |
| `_LAST_Q_ATTR = "_imgsearchv3_last_query"` | Per-editor attribute name for the last query. |
| `_get_last_query(editor)` / `_set_last_query(editor, q)` | Getter/setter. |
| `_replace_last_imgsearch_tag(html, new_tag)` | Regex find of `<img class="…imgsearch…">`, return HTML with only the **last** one replaced. Returns `None` if no match. |
| `display_image(editor, filename, field_index)` | Apply `image_placement` to `editor.note.fields[field_index]`. Skips `loadNote()` on smart-replace. |
| `_show_download_error(code)` | Map `offline`/`network`/other → user message via `utils.report`. |
| `on_search(editor)` | The main entry from the toolbar/context menu. |
| `on_previous(editor)` / `on_next(editor)` | Step the cached cursor; download & display. |
| `add_editor_buttons(buttons, editor)` | Adds the three toolbar buttons. |
| `_install_context_menu_modern()` / `_install_context_menu_legacy()` | Two implementations depending on whether `aqt.gui_hooks` is present. |
| `add_editor_context_menu_install()` | Picks one of the two. |
| `init_editor()` | Idempotent: registers hooks. |

## `addon/ui_menu.py`

Tools menu entry and the settings dialog shell. The dialog itself
is split into one file per tab under `addon/tabs/`.

| Symbol | Purpose |
| --- | --- |
| `SettingsDialog` | `QDialog` that owns the four tab widgets and a status label. |
| `SettingsDialog._save_only` | Pulls state from every tab into `self.config`, strips legacy keys, writes via `addonManager.writeConfig`. |
| `SettingsDialog._save_and_close` | Save + `accept()`. |
| `settings_dialog()` | Construct + `exec()`. |
| `init_menu()` | Idempotent: add the Tools entry. |

## `addon/tabs/`

Each tab is a `QWidget` subclass built on `TabPage` (see `_base.py`)
that exposes a small contract for the dialog:

- accepts `(config, on_dirty, parent=...)` in `__init__`,
- calls `self.mark_dirty()` whenever the user changes a setting,
- provides either a `collect()` method returning a dict to merge
  into the config, or `save_current()` writing directly into the
  shared `config` dict.

| File | Class | Owns |
| --- | --- | --- |
| `_base.py` | `TabPage` | Layout convenience, dirty callback wiring. |
| `nt_tab.py` | `NoteTypesTab` | Note-type list, query fields, image field, image placement. |
| `net_tab.py` | `NetworkTab` | Provider dropdown, Google credentials, timeout / retries / backoff. |
| `log_tab.py` | `LogsTab` | Log file path, level selector, text viewer, Refresh / Clear / Copy / Open folder / Export. |
| `support_tab.py` | `SupportTab` | Ko-fi widget, UPI / BTC / ETH QR codes with copy buttons. |
