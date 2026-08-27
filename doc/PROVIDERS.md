# Image Providers

Image Search v3 ships with four providers. The active one is chosen
by the `provider` config key (`"yandex"`, `"bing"`,
`"duckduckgo"` / `"ddg"`, or `"google"`). All four share the same
retry / timeout / backoff settings (see [CONFIG.md](CONFIG.md)) and
all four return a `list[str]` of absolute image URLs.

## Yandex (default)

- **Endpoint:** `https://yandex.ru/images/search`
- **Auth:** none.
- **Request shape:** `GET /images/search?format=json&request={"blocks":[{"block":"serp-list_infinite_yes","params":{},"version":2}]}&text=<URL-encoded query>`
- **Response:** JSON with `blocks[0].html` containing the rendered
  result list. Each result is an inline `data-bem='{…serp-item…}'`
  (or `data-bem="…"` in newer Yandex markup) JSON snippet.
- **Parser notes:** the snippet is wrapped as
  `{"serp-item": {…,"thumb":{"url":"…"},…}}`. We drill into the
  nested `serp-item` object to extract `thumb.url`. Protocol-relative
  URLs (`//avatars.example/...`) are made absolute with `https:`.
- **Caveats:** undocumented. Yandex may geo-restrict, change markup
  without notice, or rate-limit.

## Bing (keyless)

- **Endpoint:** `https://www.bing.com/images/async`
- **Auth:** none.
- **Request shape:** `GET /images/async?q=<URL-encoded query>&first=1&count=20`
- **Response:** HTML page with image results embedded as JSON inside
  `<script>` tags. The original image URLs are available as
  `&quot;murl&quot;:&quot;…&quot;` (HTML-escaped).
- **Parser notes:** we extract every `&quot;murl&quot;:&quot;…&quot;`
  occurrence, decode the entities, and dedupe. No JavaScript
  rendering required.
- **Caveats:** undocumented public endpoint; works without a key
  but Bing does not promise long-term stability. A modern Linux
  Chrome User-Agent is required (Windows UAs have been observed to
  return a JS-only page). Returns ~30–50 results per query.

## DuckDuckGo (hidden API)

- **Endpoints:**
  - `https://duckduckgo.com/` — search page, used to extract the
    per-request `vqd` token (a CSRF-like value).
  - `https://duckduckgo.com/i.js` — the image search JSON endpoint.
- **Auth:** none.
- **Request shape:**
  1. `GET /?q=<query>` → extract `vqd` from the HTML.
  2. `GET /i.js?q=<query>&vqd=<token>&o=json` → JSON with
     `results[].image` URLs.
- **Caveats:** undocumented. DDG aggressively blocks Windows
  User-Agents with 403 on the hidden `i.js` endpoint; a modern
  Linux Chrome UA works reliably. May also geo-block on shared
  IPs. On any non-2xx the request is retried with backoff; after
  that we return `[]` and the caller falls back to Yandex.

## Google Custom Search (JSON API)

- **Endpoint:** `https://www.googleapis.com/customsearch/v1`
- **Auth:** required. Both `google_api_key` and `google_cx` must be
  set, otherwise the provider returns `[]` immediately.
- **Request shape:**
  ```
  GET /customsearch/v1
    ?key=<API key>
    &cx=<CSE id>
    &q=<query>
    &searchType=image
    &safe=active
    &num=10
  ```
- **Response:** JSON with `items[].link` (direct image URLs).
- **Limitations:**
  - 10 results per request (hard API limit). We do not paginate.
  - 100 free queries/day per project, then billing.
  - 403/429 are returned as `[]` after retries.

## Fallback policy

`search._provider_results_and_label` decides the fallback target
based on `google_fallback_to_yandex`:

| Provider | Returns non-empty | Returns empty | Provider missing |
| --- | --- | --- | --- |
| `yandex` | Yandex | Yandex (empty) | n/a |
| `bing` | Bing | Yandex (fallback) | Yandex (fallback) |
| `duckduckgo` / `ddg` | DuckDuckGo | Yandex (fallback) | Yandex (fallback) |
| `google` with fallback **on** | Google | Yandex (fallback) | Yandex (fallback) |
| `google` with fallback **off** | Google | Google (empty) | Google (empty) |

`search.get_provider_label` is what the user sees in the tooltip
right after they click 🖼 — it includes the fallback message so the
user knows which provider actually returned the image.
