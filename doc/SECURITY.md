# Security

## API keys

Image Search v3 only needs API keys when the user picks
`provider = "google"`. The user enters the key and CSE id in the
settings dialog; Anki persists them in `addon/meta.json` along with
all other add-on state.

### Local file hygiene

- `addon/meta.json` is **gitignored** at the repo level. Do not
  force-add it.
- `addon/config.json` is committed and contains only empty defaults
  for the Google credentials.
- If you have ever committed a real key, treat it as compromised:
  1. Delete the key in the Google Cloud Console.
  2. Create a new one.
  3. Search the repo (`git log -p --all -S 'AIza'`) and rotate any
     matches, even if they have been removed.
  4. If the repo is public, assume the old key is scraped — rotate
     even if you only see it in old issues/PRs.

### Verifying the repo is clean

```bash
# Should print nothing
git log --all --source --oneline -- '**/meta.json'
grep -RIn 'AIza[0-9A-Za-z_-]\{35\}' --include='*.py' --include='*.json' --include='*.md' .
```

## Network safety

- All HTTPS calls use the system default certificate trust store.
  We never disable TLS verification or suppress warnings.
- Image downloads set browser-like headers (`User-Agent`, `Referer`,
  `Accept`) to reduce 403s from CDN-protected images, but no
  credentials are sent.
- The `_network_available()` check is a quick DNS probe against
  `("yandex.ru", "google.com", "1.1.1.1")`. It does not make an
  HTTP request, so it cannot leak the user's query to any third
  party.

## Add-on sandboxing

- The add-on runs inside the Anki process with full user
  permissions.
- We do not `eval` / `exec` user input.
- `image_tag` HTML-escapes the `src` value so a malicious filename
  cannot break out of the attribute.
- `mkstemp` prefixes are sanitized to `[A-Za-z0-9_-]` so a
  hostile URL cannot inject a path separator.
- `media.addFile` is called with `force_copy=True` when supported,
  so the add-on can safely delete its temp file in the same call.

## Reporting a vulnerability

Please open a GitHub issue with the `security` label or contact
the maintainer directly through the ko-fi link on the README. Do
not disclose the vulnerability publicly until a fix is available.
