# [Image Search v3](https://github.com/athulkrishna2015/Image-Search-v3)
[Install from ankiweb](https://ankiweb.net/shared/info/178037783)

Image Search v3 is a powerful Anki add-on that lets you quickly find and add images to your cards directly from the editor. It searches for images based on the content of your fields or selected text and places the chosen image into a designated field.


## Features

- **Image provider**: Yandex (default), DuckDuckGo (hidden API), or Google Custom Search (images). When using Google, enter your API key and CSE ID (cx) under Tools → Image Search v3 Settings → Network. [Requires both key and cx] [searchType=image].
- **Per-Note-Type Configuration**: Configure different query and image fields for each of your note types.
- **Smart replace**: only replaces prior images inserted by this add‑on (class "imgsearch"), preserving user text and other content; appends when no prior add‑on image exists. 
- **Graphical Settings Panel**: An easy-to-use settings panel to manage your configuration. No more manual file editing!
- **Smart Defaults**: Automatically uses the first field of a note type for searching and the last field for placing the image if not configured otherwise.
- **Search on Selection**: Simply highlight any text in the editor and use the search button or right-click context menu to search for an image.
- **Toolbar Integration**: Adds 🖼, ⬅, and ➡ buttons directly to the Anki editor toolbar for a fast workflow.
- **Right-Click Context Menu**: Right-click on highlighted text to instantly start an image search. 

## Usage

### 1. Configuration

- Open Tools → Image Search v3 Settings, select a note type on the left, then configure Query Fields, the Image Field, and Image Placement on the right, and click Save.
- Under Network, pick the provider; for Google, paste your API key and CSE ID (cx), and adjust timeout, retries, and backoff to suit your network.
- Defaults ship with an empty key/cx and provider set to Yandex, and sane network values for reliable startup on new installs.

<img width="1242" height="859" alt="Screenshot_20251104_012633" src="https://github.com/user-attachments/assets/1f66f821-6169-462f-90fa-3674c36ac1f4" />
<img width="1242" height="859" alt="Screenshot_20251104_020651" src="https://github.com/user-attachments/assets/5f56091d-61d6-4ad4-afea-beaaba3869bf" />


### 2. Searching for Images

There are three ways to search for an image in the card editor:

1.  **Using the Toolbar Button**: Click the 🖼 button on the editor toolbar.
    -   If you have text highlighted anywhere in the editor, that text will be used for the search.
    -   If no text is highlighted, the content of your configured **Query Field(s)** will be used.
2.  **Using the Right-Click Menu**: Highlight the text you want to search for, right-click it, and select **"Search image for: '...'"** from the context menu.
3.  **Browsing Results**: Use the ⬅ and ➡ buttons to browse through other image results for the last query that was performed from the query field(s).

<img width="2396" height="2044" alt="Screenshot_20251031_152224" src="https://github.com/user-attachments/assets/d311adb6-0313-4b65-9999-bc8aef374c5a" />
<img width="2396" height="2044" alt="Screenshot_20251031_152301" src="https://github.com/user-attachments/assets/f4c23fd3-0646-411a-a105-3120da3adda5" />
<img width="2396" height="2044" alt="Screenshot_20251031_152339" src="https://github.com/user-attachments/assets/ad8558af-233b-4fe5-a67f-1e869d76eb07" />

## Provider notes

- Yandex: no‑auth, undocumented JSON endpoint used by the front‑end; works well but may change, be geo‑restricted, or rate‑limited without prior notice.
- DuckDuckGo: hidden `i.js` endpoint (no API key); works best‑effort and may change, rate‑limit, or block without notice. Falls back to Yandex if no results.
- Google: official Custom Search JSON API with searchType=image; requires both [API key](https://console.cloud.google.com/apis/library/customsearch.googleapis.com?hl=en-GB) and [CSE (Google Search Engine) ID (cx)](https://programmablesearchengine.google.com/) and enforces quotas and billing on your account. 
- Routing: when provider is Google or DuckDuckGo, results are fetched first and transparently fall back to Yandex if empty, preserving the editing flow.

 If you don't know how to get the API please read this: [google custom-search](https://programmablesearchengine.google.com/)

Developer documentation lives under [doc/](./doc/) (architecture, modules,
JSON keys, errors, build, security, testing).


## Troubleshooting

### Context Menu Item Not Appearing

If the "Search image for..." option does not appear when you right-click on selected text, it might be due to a conflict with another add-on that also modifies the context menu. A common conflict is with add-ons that provide image editing or other right-click functionalities in the editor.

You can diagnose this by temporarily disabling other editor-related add-ons (like "Image Editor") via **Tools -> Add-ons**, restarting Anki, and checking if the menu item appears.

## Support

If you find this add-on useful, please consider supporting its development:

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/D1D01W6NQT)

## Changelog

The full release history is in [CHANGELOG.md](./CHANGELOG.md) (newest
first, grouped by version, with links to the corresponding GitHub
releases). Contributor and maintainer documentation (architecture,
modules, JSON keys, errors, build, security, testing) lives under
[doc/](./doc/).

### Latest changes (summary)

- **Unreleased** — network image downloads now share the same
  retry/backoff settings as the search providers; smart-replace no
  longer calls `editor.loadNote()` (preserves focus, cursor, undo);
  per-editor `last_query`; LRU touch on next/prev; sanitized
  `mkstemp` prefix; HTML-escaped `image_tag`; throttled warning
  modals; Yandex parser accepts both `data-bem` quote styles and
  protocol-relative thumb URLs; stale `query_fields: ["Front"]`
  default removed.
- **3.11.2 (2026-03-27)** — Ko-fi support widget; UPI / BTC / ETH QR
  codes on the Support tab.
- **3.11.0 (2026-03-17)** — DuckDuckGo (hidden API) provider; emoji
  toolbar labels; build scripts enforce `3.<major>.<minor>`.
- **3.9.0 (2026-02-24)** — secure TLS; hardened network config
  parsing; bounded LRU cache; idempotent hook/menu registration;
  fixed settings dialog dirty-state handling.
- **3.8.6 (2025-11-04)** — Google Custom Search (images) provider
  with fallback; per-network-tab settings; image extension inferred
  from URL; multi-host offline check.
- **3.6.x (2025-10-31)** — Smart Replace; offline-aware media
  downloads with structured error codes; per-note-type settings
  dialog; safer field resolution.

## License

This add-on is a modification of the work of original authors. Credit goes to the creators of [Anki Image Search v2](https://ankiweb.net/shared/info/432495333) and [Image Search](https://ankiweb.net/shared/info/885589449).

Toolbar buttons use emoji labels to avoid bundling image assets.

This project is licensed under the [GPLv2](./LICENSE).
