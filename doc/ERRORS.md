# Errors, Messages, and User-visible Strings

A canonical list of every message the user can see, what triggered
it, and what to do.

## Provider failures (returned by `search.getresultbyquery`)

The provider layer itself never raises to the UI. It returns `[]` on
any error and the caller (`ui_editor.on_search`) decides what to
show.

| Condition | Return | Tooltip shown | Modal shown |
| --- | --- | --- | --- |
| Provider returned URLs | first URL | `Provider: Yandex` (or DuckDuckGo/Google) | — |
| Provider returned `[]`, no fallback | `None` | `Provider: Google` | `No images found for the query (provider: Google).` |
| Provider returned `[]`, fallback succeeded | fallback URL | `Provider: Yandex (fallback from …)` | — |
| Provider returned `[]`, fallback also empty | `None` | `Provider: Yandex (fallback from …)` | `No images found for the query (provider: Yandex (fallback from …)).` |

## Download failures (returned by `utils.save_file_to_library`)

| Code | User message | Likely cause |
| --- | --- | --- |
| `None` (success) | — | image added to Anki media |
| `"offline"` | `No internet connection. Unable to download image. Please reconnect and try again.` | DNS probe failed for all configured hosts |
| `"network"` | `Network error while downloading image. Please try again in a moment.` | URL/HTTP/timeout after all retries |
| `"unexpected"` | `Could not save image to media collection.` | anything else (disk full, permission, …). A modal with the traceback is shown to the developer in the Anki console. |

## Field / configuration failures

| Condition | Modal | Throttle key |
| --- | --- | --- |
| `on_search` invoked with no selection and no configured query field content | `No text selected and no query field content found.` | — |
| `on_search` / `on_next` / `on_previous` on a note with no resolvable image field | `No destination field found on this note type.` | — |
| `on_next` / `on_previous` called before any search in this editor | `No image search yet in this editor. Press the search button first.` | — |
| `on_previous` and we are already at index 0 | `No previous image available for this query.` | — |
| `on_next` and we are already at the last index | `No next image available for this query.` | — |
| Configured `query_fields` is set but none of the field names exist on the current note type | `Could not find any of the configured query fields in the current note type. … Falling back to the first field.` | `("query_fields_missing", nt_id)` |
| Configured `image_field` does not exist on the current note type | `Could not find the configured image field (…) in the current note type (…). … Falling back to the last field: ….` | `("image_field_missing", nt_id, field_name)` |

## Settings dialog messages

| Source | Text | When |
| --- | --- | --- |
| Status label | `Saved.` | After a successful `Save` click. |
| Status label | `Could not save settings.` | If `addonManager.writeConfig` raises. |
| Status label | `Copied <Title> address to clipboard.` | After clicking one of the support-tab Copy buttons. |
| MessageBox | `You have unsaved changes for '<name>'. Save before switching?` | When switching note types in the settings dialog with `nt_dirty` true. |

## Internal log lines (developer-facing)

The add-on uses `aqt.utils.tooltip` and `aqt.utils.showWarning` for
the user. For developer visibility, the only `print` / `report`
extras are:

- `utils.report(...)` falls back to `print(text)` if `showWarning`
  cannot be imported (e.g. outside Anki).
- `utils.notify(...)` falls back to `print(text)` if neither
  `tooltip` nor `showInfo` can be imported.
- Unexpected exceptions during download are reported with the full
  traceback via `utils.report(...)`.

There is no structured logging. If you need to debug a network issue,
add `print(url, status)` in `utils._download_bytes` and inspect the
Anki console.
