# Design decisions

Guiding rule: KISS and YAGNI first. An abstraction exists only when it removes duplication
or isolates a real responsibility.

| Decision | Why |
|---|---|
| Project at repo root, not `backend/` | One deployable and nothing else in the repo. A subfolder would only add path noise. |
| Two apps: `sharing`, `shortener` | `sharing` owns lists and links. `shortener` owns code generation, `ShortRedirect` and resolution. No model or rule is duplicated. |
| One `services.py` per app, no `services/` package | Six small functions. A package would be structure without content. |
| Django ORM directly, no repository layer | The ORM already is the persistence abstraction. Reads that need a policy (404 vs 410, annotated short codes) live in `selectors.py`. |
| Services raise DRF exceptions (`NotFound`, `ValidationError`, `Gone`) | Avoids a parallel domain-exception hierarchy plus a mapping layer. Pure rules with no HTTP live in `domain.py` and `tokens.py`. |
| UUIDv4 primary keys | Required to be UUIDs. v4 is native in Python 3.13 and Django. v7 would add a dependency for no requirement. |
| Collision handling = DB unique constraint + savepoint retry (5 attempts) | Safe across processes and avoids SELECT-then-INSERT. A retry happens only when the violated constraint is the code constraint, identified by its explicit name through psycopg's `diag.constraint_name`. Any other integrity error is re-raised. |
| `SELECT … FOR UPDATE` on the list row for every write | One simple mechanism handles the 100-link race, the duplicate check, delete-vs-update, and expiry during the request. Writes to a list are rare, so serializing them per list costs nothing. The unique constraint on (`list`, `destination_url`) is the backstop. |
| Owner token = 32 random bytes, stored as SHA-256 | High-entropy secret, so a slow KDF is unnecessary. `hmac.compare_digest` compares in constant time. |
| A bearer-token "authentication" class plus an object permission | The DRF-native way to get correct `401`/`403` responses and an OpenAPI `bearer` scheme without a user model. The token is matched against the list being changed. |
| `/l/{code}` = `302` to `/api/v1/lists/{code}/` | One JSON representation of a list instead of two. Uses Django's `RedirectView`, no custom code. Unknown and expired codes get their `404`/`410` from the API URL. |
| Inactive redirect returns `410` | The record exists but is unusable, matching the rule "410 when the record still exists". `is_active` exists for future aliasing. Nothing deactivates redirects today. |
| Minimal URL normalization (trim, lowercase scheme and host, punycode hosts, empty path → `/`, drop the default port) | Exactly the RFC 3986 §6.2.3 scheme-based equivalences plus the IDNA host form, none of which change where a URL points. Punycode closes duplicate and denylist gaps between `bücher.example` and `xn--bcher-kva.example`, at the cost of showing the `xn--` form in lists. Anything more, like reordering or removing query parameters or dropping fragments, could change what the URL means. |
| Fail fast at the database (`lock_timeout=5s`, `statement_timeout=20s` in production) | Sync Gunicorn workers would otherwise sit behind a stuck lock. The statement timeout stays below Gunicorn's 30 s worker timeout, so a slow query ends in a clean error instead of a killed worker. Real lock waits are milliseconds. |
| `/healthz` as the first middleware, plus a compose healthcheck on `api` only | The in-container probe uses plain HTTP and `127.0.0.1`, which the HTTPS redirect and `ALLOWED_HOSTS` would refuse. Answering before them is safe because the response depends only on a `SELECT 1`. It gives visibility in `docker compose ps` and for a proxy or uptime monitor. Plain Compose doesn't restart unhealthy containers; crashes are covered by `restart: unless-stopped`. `cleanup` needs no healthcheck because its logs show each run. |
| **No URL reachability checks** | Fetching user-supplied URLs is the SSRF risk the spec forbids: it would let anyone probe internal hosts such as cloud metadata, `db:5432` or intranet admin pages. A safe version needs DNS pinning, private-range blocking and per-hop redirect checks. The results would also often be wrong for this audience (intranet links, logged-in tools, bot blocking), and it would need a background worker. A dead link in a 30-day list is obvious the moment someone clicks it. If ever added, it should be an informational daily status that never blocks, run from the `cleanup` container with egress restrictions. |
| `PUBLIC_BASE_URL` validated at startup | A value without a scheme would silently produce broken public URLs and turn off the block on links to our own host. Refusing to start is clearer. |
| Rate limiting with DRF `ScopedRateThrottle` + Django `DatabaseCache` | No Redis. Counters are shared across workers and instances, unlike `LocMemCache`, which multiplied every limit by the worker count. The table is created by `createcachetable` in the `migrate` service, with `MAX_ENTRIES` raised so live counters are never culled. A transaction-scoped advisory lock per (scope, client IP) serializes DRF's read-modify-write of the history, which makes the limit exact under concurrency. That's simpler than a custom counter table and keeps DRF's sliding window. Redis would not fix this on its own, because the race is in DRF's get-then-set, not in the cache backend. Limits: list creation 30/hour per IP, owner writes 600/hour per IP. Reads are not throttled. |
| Destination host policy: own host always blocked, plus the `BLOCKED_DESTINATION_HOSTS` denylist, checked on write **and** on redirect | Prevents loops and our own-domain chains, and lets operators shut down an abusive domain without database surgery. A settings list is the simplest thing that works. A database-managed blocklist or the Safe Browsing API would only be justified by a public launch. |
| Token rotation endpoint | The only remedy for a leaked token short of deleting the list. It's a small owner-only endpoint that reuses the same lock-and-check path as other writes. |
| Request-size middleware (16 KB, `413`) | DRF parsers read the stream directly and bypass `DATA_UPLOAD_MAX_MEMORY_SIZE`, so the limit is enforced on `Content-Length` before the view runs. |
| Cleanup scheduled by [supercronic](https://github.com/aptible/supercronic) in the app image (`backend/docker/crontab`, daily 03:00 UTC) | Meets "daily, no host cron, no Celery". supercronic is a widely used cron for containers: a single static binary that logs to stdout and stops cleanly on SIGTERM. It replaced a hand-written `sleep` loop to get a fixed run time and standard cron syntax. The binary is pinned to v0.2.49 and verified by SHA-256 for amd64 and arm64; that release was chosen as the newest one older than two weeks. Celery beat was rejected: the spec forbids it, and it would need a broker plus worker and beat containers for one daily job. A failed run is retried at the next 03:00, which is acceptable because the API already returns 410 for expired lists. The command takes a PostgreSQL session advisory lock, so an overlapping manual run prints "already in progress" and exits instead of deleting the same rows concurrently, which could deadlock. |
| Bundled nginx (`nginx:1.30-alpine`) as the only published service | The API needs a TLS proxy, and a tested one in the same compose file beats "bring your own" for a small deployment. It overwrites `X-Forwarded-For` (not `$proxy_add_x_forwarded_for`), so client-supplied hops never reach the rate limiter even if `DJANGO_NUM_PROXIES` is wrong. Unknown hosts get `444` or a refused TLS handshake, request bodies are buffered (sync Gunicorn workers need this) and capped, and HSTS stays in Django to avoid duplicate headers. Certificates are plain files in `TLS_CERT_DIR`, with an ACME webroot for renewals, instead of an ACME client container: one less moving part, and any CA works. `deploy/smoke-test.sh` exercises the real stack with a throwaway certificate, locally and in CI. |
| A one-shot `migrate` compose service | `api` and `cleanup` wait for it to complete successfully, which removes startup races and avoids several replicas migrating at once. The API never migrates on boot. |
| `uv.lock` + `uv sync` into the image's system Python | Reproducible, hash-locked installs without any virtualenv, inside or outside the container. |
| Base images on floating patch tags (`python:3.13-slim`, `postgres:17`) | Rebuilds pick up security patches automatically, at the cost of bit-for-bit reproducibility. Python dependencies and the supercronic and uv binaries are pinned exactly. Pin image digests if you need identical rebuilds. |
| `idna` package for host encoding | Python's built-in `idna` codec implements IDNA2003, which maps `ß`, `ς` and the zero-width joiners to other characters. `faß.example` became `fass.example`, a different domain from the one browsers visit. The widely used `idna` package (a dependency of `requests` and `httpx`) implements IDNA2008 with UTS #46 non-transitional processing, matching browsers. Locked at 3.20, released more than two weeks before adoption. |
| Destination URL limit counted in UTF-8 bytes | The unique (list, URL) index holds at most ~2.7 KB per row. A character limit let 2048 four-byte characters (8 KB) crash inserts with a 500. |
| One Dockerfile, `dev` and `prod` targets | Dev keeps test tooling and runs `runserver` against bind-mounted code. Prod has runtime dependencies only, runs as a non-root user and serves through Gunicorn. |
| JSON renderer and parser only | No browsable API, so no templates or static files beyond what drf-spectacular's docs pages need. |

## Requirement conflicts and clarifications

* **"No virtualenv" vs. uv**: uv normally creates `.venv`. With
  `UV_PROJECT_ENVIRONMENT=/usr/local` it installs into the container's interpreter instead,
  so no virtual environment exists anywhere.
* **`DATABASE_URL` and `DJANGO_DEBUG`**: dropped as redundant. The `POSTGRES_*` variables
  (which the Postgres image also uses) configure the DB, and the settings module chooses
  `DEBUG` (development `True`, production always `False`).
* **Short-code non-reuse**: codes are never reused on purpose, but deleted codes are not
  reserved. With 96-bit random codes, accidental reuse is negligible, though without a
  permanent registry it cannot be ruled out mathematically.
* **"Never return the token except on creation" vs. lost tokens**: there is deliberately
  no recovery path.
* **"Creation is the only response with the owner token" vs. rotation**: a deliberate
  extension beyond the original spec. The owner-only rotation response also returns a
  (new) token, because rotation is useless without it. No public response ever does.
