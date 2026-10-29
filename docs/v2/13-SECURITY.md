# 13: Security

V1's controls ([docs/security.md](../security.md)) all remain: 96-bit codes, hashed owner
tokens, the row-lock re-check, the advisory-locked throttles, the destination host policy,
redirect headers, size limits, the nginx hardening and the strict CSP. V2 adds accounts,
private data, server-side fetching and file handling, so the threat model grows. References:
OWASP API Security Top 10 2023 [R13], ASVS 5.0 (levels 1–2 as a review checklist) [R14], and
the OWASP SSRF [R12], redirect [R16] and file upload [R15] cheat sheets.

## Assets and trust boundaries

| Asset | Why it matters |
|---|---|
| Private list and group content, revision history | Confidentiality is a new V2 promise |
| Accounts (credentials, sessions, email addresses) | Account takeover gives control of everything the account owns |
| Legacy owner tokens (unclaimed lists) | Full control of a list until claimed or expired |
| The internal network (db, metadata endpoints, intranet) | Reachable from the worker, which fetches user-supplied URLs |
| Short-URL and directory reputation | Phishing and abuse hurt every user |
| Media storage | Uploaded files are untrusted bytes served from our origin |

Trust boundaries: browser ↔ nginx (TLS), nginx ↔ api (internal network), worker ↔ internet
(**new**, outbound), and api/worker ↔ PostgreSQL.

## Threats and mitigations

| Threat (prompt Part 14) | Mitigation | Verified by |
|---|---|---|
| **Anonymous sharing** | Only `unlisted` and `public` lists are readable without an account. Creation needs an account ([ADR-011](adr/ADR-011-accounts-required-legacy-lists.md)) | API matrix tests |
| **Private collections** | The policy plus SQL-filtered querysets. 404 for unauthorized ([12](12-AUTHORIZATION.md)) | matrix and leak tests |
| **Unlisted URLs** | Unchanged capability semantics: 96-bit codes, `no-referrer`, `noindex`. Never shown in the directory or in public groups | directory and group leak tests |
| **Creator-token migration** | Claim needs a session and the token, runs under the lock, retires the token, and stores and logs only hashes ([06](06-MIGRATION-PLAN.md#ownership-transition)) | claim tests (double claim, wrong token, expired) |
| **Authentication** | django-allauth headless: Django password hashing (PBKDF2 default) and the 4 default password validators, email verification, built-in rate limits on login and reset, enumeration prevention on signup and reset responses [R6] | auth API tests, e2e |
| **Authorization / permission escalation** | One policy module. Owner-only settings and members. Role changes by the owner only. A user can't grant a role higher than their own. Group roles never reach lists | matrix tests including escalation attempts |
| **IDOR / BOLA** [R13] | Every lookup starts from the parent resource and the visible queryset. Link UUIDs are always scoped to their list (V1 `_get_link` pattern). Nested ids are never trusted alone | tests swapping ids across lists and groups |
| **Short URL enumeration** | 96-bit random codes (V1). Private targets answer 404 like unknown codes | V1 tests + visibility tests |
| **SSRF** | The [SSRF-safe fetcher](#ssrf-safe-fetcher) in the worker only. The api process never fetches user URLs | fetcher unit tests with simulated DNS rebinding |
| **XSS** | Vue escapes by default. `v-html` is banned for user or fetched content (lint rule). Fetched strings are stored as plain text. SVG is never accepted. The CSP stays `script-src 'self'` (default-src). Link `href`s are always our `/r/` short URL or a server-validated http(s) URL | lint, component tests, CSP smoke test |
| **CSRF** | New with cookies: `CsrfViewMiddleware` and DRF `SessionAuthentication` enforce CSRF on authenticated unsafe requests [R8]. `SameSite=Lax` session cookie. Remove V1's `security.W003` silence. Legacy bearer requests carry no ambient credentials, so they need no CSRF | API tests without and with a wrong token; `check --deploy` in CI |
| **Malicious URL schemes** | Server-side http/https only (V1 `normalize_destination_url`), also for metadata-derived image URLs. `HttpResponseRedirect` refuses other schemes (V1) | V1 tests + new ones |
| **Open redirects** | `/r/` redirects only to stored, validated URLs (V1). `next`/redirect parameters must be same-origin paths. allauth redirect settings point to SPA routes only [R16] | tests for `next=//evil`, `next=https://…` |
| **Metadata fetching** | Fetcher policy plus size, time and type limits, results stored as text, failures as codes | fetcher tests |
| **File and image handling** | The [media pipeline](#media): type sniffing, pixel limits, re-encode, random paths, `nosniff`, a sandbox CSP on `/media/` [R15] | image tests (polyglots, bombs, wrong types) |
| **Rate limiting** | [Rate limits](#rate-limits) per user or IP, DB-backed (V1 mechanism) | throttle tests incl. concurrency (V1 style) |
| **Sensitive data leakage** | No tokens, session ids, CSRF tokens or email addresses in logs. Emails are visible only to their owner. Owner names only on public lists. History only for editors ([12](12-AUTHORIZATION.md#leak-analysis)) | log-capture tests (V1 has one for tokens) |
| **Expired and deleted resources** | V1 semantics: 410 from expiry, purge, tombstoned links 404, deleted lists 404, sync status for orphaned children | V1 tests + new ones |
| **Concurrent permission changes** | Authorization re-checked under the aggregate lock. Membership changes take the same lock ([12](12-AUTHORIZATION.md#concurrent-permission-changes)) | concurrency test: revoke during a write |
| **Phishing via public lists or directory** | V1 denylist (applied on write and on redirect). Making something public needs a **verified email**. Operator commands to unpublish or delete. A report button is a later enhancement | tests for the verified-email gate |

## SSRF-safe fetcher

`metadata/fetcher.py` is the **only** code that fetches user-supplied URLs (CLAUDE.md). It
follows OWASP's "Case 2" guidance for arbitrary external destinations [R12]:

1. **Input:** the stored, normalized URL. Re-run `normalize_destination_url` and the host
   policy (own hosts and `BLOCKED_DESTINATION_HOSTS`). Schemes http/https only. **Ports 80
   and 443 only**: links on other ports simply get no metadata, which removes internal-service
   probing on odd ports.
2. **Resolve** A and AAAA records. **Every** address must be globally routable:
   `ipaddress.ip_address(a).is_global`, with IPv4-mapped and 6to4 IPv6 addresses unwrapped
   first. Explicit denies cover `0.0.0.0/8`, `127.0.0.0/8`, RFC 1918, `100.64.0.0/10`,
   `169.254.0.0/16` (cloud metadata), `fc00::/7`, `fe80::/10`, multicast and `::1`. Any
   non-global answer rejects the URL. A blocklist is the only option for open-ended
   destinations, and OWASP calls it necessary but not sufficient, hence the steps below.
3. **Pin the connection** to the validated address. Use the original hostname for the `Host`
   header, TLS SNI and certificate verification. Never let the HTTP client resolve the name
   again, because that second lookup is the DNS-rebinding gap [R12]. Implementation: urllib3
   2.x connection pools opened on the IP with `server_hostname` and `assert_hostname` set to
   the original host. The surveyed SSRF wrapper libraries (drawbridge, ssrfguard,
   httpx-secure, Champion/Advocate) have unverified maintenance [R30], so we own about 150
   lines with exhaustive tests instead.
4. **Redirects off.** Follow up to 3 manually. Each hop re-runs steps 1–3. A relative hop
   resolves against the current URL.
5. **Limits:** connect 3 s, read 5 s, 10 s wall clock per URL. HTML ≤512 KB and images ≤1 MB,
   counted **after** decompression. Stop reading at the limit.
6. **Content types:** pages `text/html` or `application/xhtml+xml`. Images png, jpeg, gif,
   webp, x-icon. Anything else is ignored. SVG is never fetched or stored.
7. **Request hygiene:** a fixed `User-Agent` naming the service, no cookies, no auth headers,
   no `Referer`.
8. **Parsing:** the stdlib `html.parser` over the capped bytes. Extract `<title>`,
   `meta[name=description]`, `og:title`, `og:description`, `og:image`, `og:site_name` [R20], and
   `link[rel~=icon]` / `apple-touch-icon`, falling back to `/favicon.ico`. Values are trimmed,
   control characters removed, and truncated to field limits. HTML is never stored.
9. **Throughput and abuse:** worker concurrency 2. At most one refresh per link per hour. Link
   creation is already throttled. One request per host per second per worker.
10. **Network layer (defence in depth, recommended):** a host firewall rule (`DOCKER-USER`
    chain) that drops worker egress to private ranges and `169.254.169.254`. It is optional,
    because the application-layer pinning is the primary control
    ([14](14-INFRASTRUCTURE.md#worker-egress)).

## Media

Uploaded images (list and group image, link icon) and fetched icons and images go through one
Pillow pipeline (Pillow 13.0 current [R24]) [Decision, ADR-012]:

1. Uploads ≤2 MB (a per-route request limit, [09](09-API-DESIGN.md#uploads)). Fetched images
   ≤1 MB.
2. Identify by content, never by name or `Content-Type`. Allow PNG, JPEG, WebP, GIF (first
   frame) and ICO (fetched only). Set `Image.MAX_IMAGE_PIXELS` to 16 MP and treat Pillow's
   `DecompressionBombWarning` as an error.
3. `verify()`, reopen, `load()`, apply `exif_transpose`, convert to RGBA, `contain` into
   128×128 (icons) or 512×512 (list or group images), and **re-encode** to WebP. Re-encoding
   destroys polyglots and embedded payloads [R15] and strips EXIF and GPS metadata.
4. Store at `media/{kind}/{hh}/{sha256}.webp`, content-addressed, so files are never
   overwritten and are deduplicated.
5. nginx serves `/media/` with `X-Content-Type-Options: nosniff`, an explicit
   `image/webp` type, `Content-Security-Policy: default-src 'none'; sandbox` and
   `Cache-Control: public, max-age=31536000, immutable`. Images are never served by Django.
6. Unreferenced files are removed by `cleanup` after 7 days
   ([14](14-INFRASTRUCTURE.md#scheduled-jobs)).

Accepted risk: media URLs aren't access-checked. Their 256-bit content-hash names can only be
guessed by someone who already has the image. Moving private images behind an authenticated
`X-Accel-Redirect` is a later option if icons ever become sensitive.

## Sessions, cookies and headers

- Session cookie: `Secure` (production), `HttpOnly`, `SameSite=Lax`, two-week age, rotated on
  login (Django). The CSRF cookie is readable by JavaScript (needed by the SPA), `Secure`, and
  `CSRF_TRUSTED_ORIGINS = [PUBLIC_BASE_URL]`.
- Email verification and password-reset keys travel in the URL **fragment**
  (`/reset-password#key=…`). Browsers never send fragments to servers, so the keys stay out of
  nginx logs, as V1's edit-link tokens do. The SPA removes them from the address bar on
  arrival. Reset keys work once.
- `?next=` after sign-in accepts only same-site paths (`safeRedirectPath`). It rejects `//host`,
  `/\host`, other schemes, and control characters that browsers strip into `//host`.
- Production keeps HSTS, the SSL redirect and the proxy header from V1. `check --deploy
  --fail-level WARNING` stays in CI, without the W003 silence.
- The nginx CSP for the SPA is unchanged (`default-src 'self'; img-src 'self' data:; …`).
  Media is same-origin, so no third-party image hosts are allowed. That also means visitors'
  IPs never leak to icon hosts.
- `X-Robots-Tag: noindex` stays for everything in the MVP. Indexing public lists is an open
  question ([20](20-DECISIONS-AND-OPEN-QUESTIONS.md)).

## Rate limits

DRF scoped throttles (V1 mechanism) are keyed by user when signed in and by IP otherwise.
These are initial values. Tune them from logs.

| Scope | Limit |
|---|---|
| Login and password reset | allauth defaults (failed login per IP and account) |
| Signup | 10/h per IP |
| List and group creation | 60/h per user |
| Content writes (lists, links, groups, reorder) | 1200/h per user; legacy token writes 600/h per IP (V1) |
| Uploads | 120/h per user |
| Metadata refresh | 60/h per user, 1/h per link |
| Sync apply (postponed), restore, claim | 120/h per user |
| Directory search | 600/h per IP |
| Adding members by email | 60/h per user |

## Logging and secrets

Logs record ids (list, link, user, sync record) and error codes. They never record tokens,
session or CSRF values, or email addresses (use the user id). V1's test that tokens never
appear in logs is extended to sessions and claim. Secrets stay environment-only. New secrets
are SMTP credentials and optionally `SENTRY_DSN` ([14](14-INFRASTRUCTURE.md)).

## Residual risks (accepted)

- Account enumeration when an owner adds a member by email (verified owners only, rate-limited,
  one generic answer for unknown and unverified addresses).
- Media isn't access-controlled (unguessable names).
- Rate limits are per IP for anonymous users (V1 limitation, unchanged).
- Phishing through public lists is reduced (verified email, denylist, operator unpublish) but
  not solved. There is no automated reputation check. That is a later option for a fully
  public launch (V1 `docs/security.md` reasoning still holds).
