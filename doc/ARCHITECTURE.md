# Architecture

## Goal

Allow an Anki card editor user to insert an image found by an online
image search without leaving the editor, with per-note-type configuration
and three different image search providers.

## Components

```
                ┌───────────────────────────────────────┐
                │          Anki main window             │
                │  ┌─────────────────────────────────┐  │
                │  │  Editor toolbar + context menu  │  │
                │  │   🖼  ⬅  ➡  (ui_editor.py)     │  │
                │  └──────────────┬──────────────────┘  │
                │                 │ on_search/on_next/   │
                │                 │ on_previous          │
                │                 ▼                      │
                │  ┌─────────────────────────────────┐  │
                │  │       search.py (cache)         │  │
                │  │  RESULTS / INDICES / PROVIDERS  │  │
                │  └────┬─────────────┬────────┬─────┘  │
                │       │             │        │        │
                │       ▼             ▼        ▼        │
                │  yimages.py   gimages.py   ddg_…      │
                │  (Yandex)     (Google)     (DuckDuckGo)│
                │       │             │        │        │
                │       └─────────────┴────────┘        │
                │                     │                  │
                │                     ▼                  │
                │            utils.save_file_to_         │
                │               library                  │
                │                     │                  │
                │                     ▼                  │
                │   Anki media collection (addFile)      │
                │                     │                  │
                │                     ▼                  │
                │         display_image → editor field  │
                └───────────────────────────────────────┘

                ┌───────────────────────────────────────┐
                │  Tools → Image Search v3 Settings     │
                │             (ui_menu.py)               │
                │   • Note Types tab (per model)         │
                │   • Network tab   (provider, retries)  │
                │   • Support tab   (Ko-fi, QR codes)    │
                └────────────────────┬──────────────────┘
                                     │ writes to
                                     ▼
                          addon/meta.json (Anki-managed,
                          not in git) and addon/config.json
                          (defaults shipped with the add-on)
```

## Lifecycle

1. **Module load** — Anki imports `addon/__init__.py`, which calls
   `setup()`. This in turn imports and runs `init_editor()` and
   `init_menu()`.
2. **Hook installation** — `init_editor` registers:
   - `setupEditorButtons` → adds the three toolbar buttons to every
     new editor.
   - `EditorWebView.contextMenuEvent` (legacy) **or**
     `gui_hooks.editor_will_show_context_menu` (modern) → adds the
     "Search image" / "Search image for selection" entry.
3. **Menu installation** — `init_menu` adds a single
   `Image Search v3 Settings` action under Tools.
4. **Per-editor interaction** — clicking 🖼/⬅/➡ calls the
   corresponding `on_search` / `on_next` / `on_previous`. The editor
   instance stores `_imgsearchv3_last_query` between calls.
5. **Per-provider call** — `search.getresultbyquery(q)` is the only
   entry point to the providers. It picks the configured provider,
   caches the resulting URL list in `RESULTS`, and returns the current
   index. `getnextresultbyquery` / `getprevresultbyquery` only mutate
   the index, no network.
6. **Image fetch & write** — `utils.save_image_to_library` is the
   single download path. It:
   - Checks offline with a quick DNS probe (`_network_available`).
   - Picks a safe file prefix and suffix.
   - Streams the image to a `mkstemp` temp file with retry+backoff.
   - Calls `media.addFile(temp_path, force_copy=True)` (falling back
     to `addFile(temp_path)` on older Anki).
   - Always deletes the temp file in `finally`.
7. **Image placement** — `display_image` is called with the final
   filename and the resolved field index. It applies the per-note-type
   `image_placement` policy:
   - `replace` (smart): swap the most recent `<img class="imgsearch" …>`
     in the field, leave everything else intact. **Does not** call
     `editor.loadNote()` so focus/undo are preserved.
   - `append` / `prepend`: append/prepend the new tag, then call
     `editor.loadNote()` to refresh the view.

## Boundaries

- The add-on never blocks the editor waiting for a single request:
  every network call uses `requests` with a per-request `timeout`
  and a bounded retry loop. If the loop is exhausted it returns an
  empty list and the UI surfaces a concise error.
- The add-on never writes to disk outside of the OS-managed Anki
  media folder. Temp files are always deleted.
- The add-on never imports `aqt.qt` symbols at module import time in
  `utils`, `search`, `yimages`, `gimages`, or `ddg_hidden_test` —
  those modules are safe to import from non-GUI code (tests, build
  scripts).

## Threading

All operations run on the Anki main (Qt GUI) thread. We do not
spawn background workers. This is intentional: Anki's media DB and
editor objects are not thread-safe, and the image downloads are
short enough that a UI freeze is acceptable.
