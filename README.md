# listlinkedin: temporary link lists with a built-in URL shortener

An anonymous backend for team bonding. Someone creates a list, adds interesting links and
shares the list URL with colleagues. Anyone with the URL can read the list. Only the
creator, who holds a private **owner token**, can change it. The whole list expires
**30 days after creation**.

No accounts, no login, no frontend: a Django REST API plus two short-URL namespaces:

| URL | Meaning |
|---|---|
| `/l/{list_code}` | Public list URL: `302` redirect to `/api/v1/lists/{list_code}/` (JSON) |
| `/r/{redirect_code}` | Short URL of one link: `302` redirect to its current destination |

Everything runs in Docker. You need only Docker Engine/Desktop with Compose, Git and an
editor. No virtualenv and no host Python.

---

## Quick start

```bash
docker compose up --build -d      # db + migrations + api + cleanup
docker compose logs -f api
open http://localhost:8000/api/docs/   # Swagger UI
docker compose down               # stop (add -v to also drop the database volume)
```

This works from a clean checkout. `compose.yaml` has development defaults, so a `.env` is
optional (copy `.env.example` to override values).

## Architecture

A modular monolith with two Django apps and an explicit boundary:

```text
config/                 settings (base / development / production), urls, wsgi, middleware
apps/sharing/           owns lists and links
  models.py             SharedList, SharedLink
  domain.py             business rules: 30-day lifetime, 100-link cap, URL normalization
  tokens.py             owner token generation, SHA-256 hashing, constant-time verify
  services.py           all writes (transactions + row locks)
  selectors.py          reads (404 vs 410 decision, links annotated with short code)
  permissions.py        bearer-token auth, per-list owner permission, write throttle
  serializers.py, views.py, urls.py
  management/commands/cleanup_expired.py
apps/shortener/         owns short codes and redirect mappings
  generators.py         secrets-based 16-char Base64URL codes
  models.py             ShortRedirect
  services.py           collision-safe code insertion, redirect creation and resolution
  views.py              GET /r/{code}
tests/integration/      full HTTP workflow against PostgreSQL
compose.yaml            development stack  ·  compose.prod.yaml  production stack
```

Request flow: **view** (HTTP, serializers, permissions) → **service** (transaction, lock,
rules) → **Django ORM**. `sharing` calls `shortener.services.create_redirect()` when a
link is created. `shortener` only follows `ShortRedirect → SharedLink → SharedList` to
check expiration.

Docker services:

| Service | Role |
|---|---|
| `db` | `postgres:17`, named volume `pgdata`, `pg_isready` health check |
| `migrate` | One-shot `manage.py migrate`. Starts only once `db` is healthy |
| `api` | Django (dev: `runserver` with bind-mounted code and auto-reload; prod: Gunicorn). Health check every 30 s against `/healthz`, which includes a database round-trip. Shown in `docker compose ps`. Compose only marks an unhealthy container; it doesn't restart it. |
| `cleanup` | Same image. [supercronic](https://github.com/aptible/supercronic) runs [`docker/crontab`](docker/crontab): `cleanup_expired` daily at 03:00 UTC. No host cron, Celery or Redis. |

`api` and `cleanup` start only after `migrate` has **completed successfully**, so nothing
talks to PostgreSQL before it is ready and migrated.

## Database

```text
SharedList 1 ──< SharedLink 1 ──< ShortRedirect
 (ON DELETE CASCADE)        (ON DELETE CASCADE)
```

| Table | Key columns | Constraints and indexes |
|---|---|---|
| `SharedList` | `id` UUIDv4 PK, `public_code` (16), `owner_token_hash` (64, SHA-256 hex), `title`, `created_at`, `updated_at`, `expires_at` | unique `public_code`; index on `expires_at` (cleanup) |
| `SharedLink` | `id` UUIDv4 PK, `shared_list` FK, `destination_url` TEXT (normalized), `title` NULL | unique (`shared_list`, `destination_url`); FK index |
| `ShortRedirect` | `id` UUIDv4 PK, `code` (16), `link` FK, `is_active`, `created_at` | unique `code`; FK index |

Each link gets exactly one active redirect today. The FK leaves room for aliases later
(not implemented).

## Development commands (all inside Docker)

```bash
docker compose exec api python manage.py migrate
docker compose exec api python manage.py makemigrations
docker compose exec api python manage.py check
docker compose exec api python manage.py cleanup_expired
docker compose run --rm api ruff check . && docker compose run --rm api ruff format .
```

Dependencies are declared in `pyproject.toml` and locked in `uv.lock`. The image installs
them with `uv sync --locked` straight into the container's system Python. After changing
dependencies, regenerate the lock inside a container and rebuild:

```bash
docker run --rm -v "$PWD":/app -w /app ghcr.io/astral-sh/uv:0.9.5-python3.13-bookworm-slim uv lock
docker compose up --build -d
```

> Dev containers run as the image's root user so files created through the bind mount
> (e.g. new migrations) belong to you under rootless Docker. With classic (rootful) Docker,
> add `--user "$(id -u):$(id -g)"` to `docker compose run`/`exec` commands that write files.

## Testing

```bash
docker compose run --rm api pytest
```

Tests run against a real PostgreSQL test database (created automatically by pytest-django)
and cover lists, links, ownership, the shortener (including simulated code collisions),
expiration, cleanup, a real multi-threaded race for the 100-link limit, and an end-to-end
workflow in `tests/integration/`.

**CI:** [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on every pull request
and every push to `main`, and can be started by hand from the Actions tab. It uses the same
Docker commands as above, in this order: ruff lint and format check, migrations up to date,
the full test suite against PostgreSQL, then a production image build with
`check --deploy --fail-level WARNING`.

## API

Interactive docs: **http://localhost:8000/api/docs/** (Swagger) ·
**/api/redoc/** · raw schema: **/api/schema/**

| Method | Path | Access |
|---|---|---|
| `POST` | `/api/v1/lists/` | public (rate-limited) |
| `GET` | `/api/v1/lists/{list_code}/` | public |
| `PATCH` | `/api/v1/lists/{list_code}/` | owner (title only) |
| `DELETE` | `/api/v1/lists/{list_code}/` | owner |
| `POST` | `/api/v1/lists/{list_code}/rotate-token/` | owner (returns a new token; the old one stops working) |
| `GET` | `/api/v1/lists/{list_code}/links/` | public, paginated (`?page=`, `?page_size=` ≤ 100, default 20), newest first |
| `POST` | `/api/v1/lists/{list_code}/links/` | owner |
| `PATCH` | `/api/v1/lists/{list_code}/links/{link_id}/` | owner (title, destination_url) |
| `DELETE` | `/api/v1/lists/{list_code}/links/{link_id}/` | owner |
| `GET` | `/r/{redirect_code}` | public, `302` + `Cache-Control: no-store`, `Referrer-Policy: no-referrer` |
| `GET` | `/l/{list_code}` | public, `302` to the list's API URL |
| `GET` | `/healthz` | public, `200 {"status":"ok"}` or `503` when the database is unreachable |

`/r/` and `/l/` also accept a trailing slash, since some apps add one when links are
pasted. The URLs the API hands out never include one.

Status codes: `401` missing token · `403` token doesn't own this list · `404` unknown or
deleted · `410` expired (or inactive redirect) · `400` validation (bad URL, duplicate,
100-link limit) · `413` body > 16 KB · `429` rate limited.

Link rules: only `http`/`https`; no `user:pass@`; at most 2048 bytes in UTF-8 (so
non-ASCII characters count more); must be a
well-formed URL; not pointing at this service (any name in `PUBLIC_BASE_URL` or
`DJANGO_ALLOWED_HOSTS`) or at a host in `BLOCKED_DESTINATION_HOSTS`. Blocking a host
later also makes existing short URLs to it return `410`. Duplicates are detected after a
deliberately minimal normalization that only applies meaning-preserving equivalences:
trim whitespace, lowercase the scheme and host, store internationalized hosts in punycode
using the same IDNA2008/UTS #46 rules as browsers (`bücher.example` →
`xn--bcher-kva.example`, and `faß.example` stays distinct from `fass.example`), turn an
empty path into `/`, and drop the
default port (`:80` for http, `:443` for https). The path, query order and fragment are
otherwise never altered. Unparseable URLs and ports outside 1–65535 are rejected with
`400`.

The server checks that links are *well-formed* but never fetches them to see whether they
respond. That's deliberate: see "No URL reachability checks" in
[docs/decisions.md](docs/decisions.md).

### curl walkthrough

```bash
BASE=http://localhost:8000

# 1. Create a list (public endpoint).
curl -s -X POST $BASE/api/v1/lists/ -H 'Content-Type: application/json' \
     -d '{"title": "Friday Team Bonding"}' | tee list.json
# {"id":"…","public_code":"X7pKm2Qv8Nw4Rs6A","public_url":"http://localhost:8000/l/X7pKm2Qv8Nw4Rs6A",
#  "title":"Friday Team Bonding","created_at":"…","expires_at":"…","owner_token":"<PRIVATE>"}

# 2. Extract values. CODE / public_url are PUBLIC, so share them. TOKEN is PRIVATE, keep it.
CODE=$(python3 -c 'import json;print(json.load(open("list.json"))["public_code"])')
TOKEN=$(python3 -c 'import json;print(json.load(open("list.json"))["owner_token"])')
#    (or with jq:  CODE=$(jq -r .public_code list.json); TOKEN=$(jq -r .owner_token list.json))

# 3. Add a link (owner only).
curl -s -X POST $BASE/api/v1/lists/$CODE/links/ \
     -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
     -d '{"title": "Interesting Article", "destination_url": "https://example.com/article"}'
# {"id":"<LINK_ID>", …, "short_url":"http://localhost:8000/r/Ab3Kp7Nq2Wz8Lm5R"}
LINK_ID=<LINK_ID>; SHORT=Ab3Kp7Nq2Wz8Lm5R

# 4. View the list anonymously (no token): metadata, then links.
curl -s $BASE/api/v1/lists/$CODE/
curl -s $BASE/api/v1/lists/$CODE/links/

# 5. Update the destination (owner only). The short URL does not change.
curl -s -X PATCH $BASE/api/v1/lists/$CODE/links/$LINK_ID/ \
     -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
     -d '{"destination_url": "https://example.com/new-article"}'

# 6. Resolve the short URL: 302 to the *current* destination.
curl -si $BASE/r/$SHORT | grep -i '^location'
# Location: https://example.com/new-article

# 7. Delete the link (owner only). Its short URL now returns 404.
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE \
     -H "Authorization: Bearer $TOKEN" $BASE/api/v1/lists/$CODE/links/$LINK_ID/   # 204

# 8. Token leaked? Rotate it (owner only). The old token is rejected from now on.
TOKEN=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" \
        $BASE/api/v1/lists/$CODE/rotate-token/ | python3 -c 'import sys,json;print(json.load(sys.stdin)["owner_token"])')

# 9. Delete the whole list (owner only). Links, short URLs and the token all stop working.
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE \
     -H "Authorization: Bearer $TOKEN" $BASE/api/v1/lists/$CODE/   # 204
```

## Ownership

* `POST /api/v1/lists/` returns `owner_token` **once**. Only the owner-only rotation
  endpoint ever returns a token again (a new one), and the database stores only SHA-256
  digests.
* If a token may have leaked, call `POST /api/v1/lists/{list_code}/rotate-token/` with it.
  The response holds the new token, and the old one is revoked immediately. Deleting the
  list revokes the token as well.
* Send it as `Authorization: Bearer <owner_token>` on owner-only requests. Never put it
  in URLs or query strings.
* Tokens are checked against the specific list being changed (constant-time comparison),
  so one list's token cannot modify another list.
* **A lost token cannot be recovered.** There are no accounts and no reset flow. The list
  stays readable until it expires but can no longer be changed.

## Expiration

* `expires_at = created_at + 30 days` (UTC), set at creation and never changed. Editing the
  title or links does not extend it.
* Every request checks expiration against the stored timestamp. From the exact expiry
  instant, the list, its links and its short URLs return `410 Gone`, even before cleanup.
  The check is repeated under the row lock during writes.
* The `cleanup` service uses [supercronic](https://github.com/aptible/supercronic) to run
  `cleanup_expired` daily at 03:00 UTC, as set in [`docker/crontab`](docker/crontab). Edit
  that file to change the schedule, then restart with `docker compose up -d`. The command
  deletes expired lists in batches of 500 using short transactions, cascading to links and
  redirects, prunes expired rate-limit entries, and reports the counts in
  `docker compose logs cleanup`. It is idempotent, so running it again is harmless. To run
  it immediately: `docker compose exec cleanup python manage.py cleanup_expired`.
* Physical deletion can lag expiry by up to about 24 hours. A run that fails is retried
  the next night. After deletion, the same URLs return `404`.

## Deployment

1. `cp .env.example .env` and set real values: a long random `DJANGO_SECRET_KEY`,
   `DJANGO_ALLOWED_HOSTS`, database credentials, `PUBLIC_BASE_URL=https://your.domain`, and
   `DJANGO_NUM_PROXIES` (number of reverse proxies in front of the API). Optionally set
   `BLOCKED_DESTINATION_HOSTS` to denylist abusive domains. After changing it, restart
   with `up -d` and the new list takes effect, including for short URLs already shared.
2. Put a TLS-terminating reverse proxy on the same host in front of `127.0.0.1:8000` that
   sets `X-Forwarded-Proto` and `X-Forwarded-For`. **All management traffic must use
   HTTPS.** The API is published on loopback only. Don't expose port 8000 publicly: direct
   clients could bypass HTTPS and spoof the forwarded headers. If the proxy runs on another
   machine, use a private network or a firewall rule instead. The proxy must **buffer
   requests**: Gunicorn's sync workers can otherwise be tied up by slow clients. nginx does
   this by default; with Traefik or similar, enable request buffering.
3. Start the stack:

   ```bash
   docker compose -f compose.prod.yaml up --build -d
   docker compose -f compose.prod.yaml exec api python manage.py check --deploy
   ```

The production image (`prod` target) has no dev dependencies, runs as a non-root `app`
user, and serves through Gunicorn (`WEB_CONCURRENCY` workers, 30 s timeout, access log to
stdout). Production settings enable the SSL redirect, HSTS, the proxy SSL header, secure
cookies, persistent DB connections with health checks, and `DEBUG=False`.

More detail: [docs/decisions.md](docs/decisions.md) (design decisions and trade-offs) and
[docs/security.md](docs/security.md) (threat model and limitations).
