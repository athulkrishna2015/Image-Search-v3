# Image Providers

Image Search v3 ships with three providers. The active one is chosen
by the `provider` config key (`"yandex"`, `"duckduckgo"` / `"ddg"`,
or `"google"`). All three share the same retry / timeout / backoff
settings (see [CONFIG.md](CONFIG.md)) and all three return a
`list[str]` of absolute image URLs.

## Yandex (default)

- **Endpoint:** `https://yandex.ru/images/search`
- **Auth:** none.
- **Request shape:** `GET /images/search?format=json&request={"blocks":[{"block":"serp-list_infinite_yes","params":{},"version":2}]}&text=<URL-encoded query>`
- **Response:** JSON with `blocks[0].html` containing the rendered
  result list. Each result is an inline `data-bem='{…serp-item…}'`
  (or `data-bem="…"` in newer Yandex markup) JSON snippet.
- **Parser notes:** we extract every `data-bem` attribute whose value
  contains `"serp-item"`, decode the JSON, and pull `thumb.url`. The
  returned URL is protocol-relative (`//avatars.example/...`); we
  prepend `https:`.
- **Caveats:** undocumented. Yandex may geo-restrict, change markup
  without notice, or rate-limit.

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
- **Caveats:** undocumented. Will return HTTP 202/403 if rate-limited
  or blocked. On any non-2xx the request is retried with backoff;
  after that we return `[]` and the caller falls back to Yandex.

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
| `duckduckgo` / `ddg` | DuckDuckGo | Yandex (fallback) | n/a |
| `google` with fallback **on** | Google | Yandex (fallback) | Yandex (fallback) |
| `google` with fallback **off** | Google | Google (empty) | Google (empty) |

`search.get_provider_label` is what the user sees in the tooltip
right after they click 🖼 — it includes the fallback message so the
user knows which provider actually returned the image.
