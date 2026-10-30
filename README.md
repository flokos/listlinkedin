# listlinkedin: temporary link lists with a built-in URL shortener

An anonymous backend for team bonding. Someone creates a list, adds interesting links and
shares the list URL with colleagues. Anyone with the URL can read the list. Only the
creator, who holds a private **owner token**, can change it. The whole list expires
**30 days after creation**.

No accounts, no login: a Django REST API, a Vue frontend ([frontend/](frontend/)) and two
short-URL namespaces:

| URL | Meaning |
|---|---|
| `/l/{list_code}` | Public list URL: the list's page in the Vue app |
| `/r/{redirect_code}` | Short URL of one link: `302` redirect to its current destination |

Everything runs in Docker. You need only Docker Engine/Desktop with Compose, Git and an
editor. No virtualenv and no host Python.

---

## Quick start

```bash
docker compose up --build -d      # db + migrations + api + cleanup + frontend
docker compose logs -f api
open http://localhost:5173/            # the Vue app (Vite dev server, hot reload)
open http://localhost:8000/api/docs/   # Swagger UI
docker compose down               # stop (add -v to also drop the database volume)
```

This works from a clean checkout. `compose.yaml` has development defaults, so a `.env` is
optional (copy `.env.example` to override values).

## Architecture

A modular monolith with two Django apps and an explicit boundary:

```text
backend/                Django API (its own Docker build context)
  config/               settings (base / development / production), urls, wsgi, middleware
  apps/sharing/         owns lists and links
    models.py             SharedList, SharedLink
    domain.py             business rules: 30-day lifetime, 100-link cap, URL normalization
    tokens.py             owner token generation, SHA-256 hashing, constant-time verify
    services.py           all writes (transactions + row locks)
    selectors.py          reads (404 vs 410 decision, links annotated with short code)
    permissions.py        bearer-token auth, per-list owner permission, write throttle
    serializers.py, views.py, urls.py
    management/commands/cleanup_expired.py
  apps/shortener/       owns short codes and redirect mappings
    generators.py         secrets-based 16-char Base64URL codes
    models.py             ShortRedirect
    services.py           collision-safe code insertion, redirect creation and resolution
    views.py              GET /r/{code}
  tests/integration/    full HTTP workflow against PostgreSQL
  Dockerfile, pyproject.toml, uv.lock, docker/crontab
frontend/               Vue 3 + Vuetify app; its Dockerfile also builds the production nginx
deploy/                 nginx proxy config and production smoke test
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
| `frontend` | Development only: Vite dev server on port 5173 with bind-mounted sources and hot reload. Proxies `/api/` and `/r/` to `api`, so the app sees one origin as it does behind nginx. In production the built app is served by `nginx` instead. |
| `worker` | V2 (task 7.1). Same image, `manage.py db_worker`: runs background tasks from a queue table in PostgreSQL ([ADR-008](docs/v2/adr/ADR-008-background-metadata-extraction.md)). Health check `check_worker` (unhealthy if a task waits or runs over 10 minutes). Two replicas in production (`WORKER_REPLICAS`). |
| `cleanup` | Same image. [supercronic](https://github.com/aptible/supercronic) runs [`backend/docker/crontab`](backend/docker/crontab): `cleanup_expired` daily at 03:00 UTC, plus the V2 jobs listed there (sessions, task records, stuck tasks, accounts, media). No host cron, Celery or Redis. |
| `mailpit` | Development only (V2 accounts): catches the mail the app sends, so nothing leaves your machine. Read it at http://localhost:8025. |

`api`, `worker` and `cleanup` start only after `migrate` has **completed successfully**, so nothing
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
docker run --rm -v "$PWD/backend":/app -w /app ghcr.io/astral-sh/uv:0.9.5-python3.13-bookworm-slim uv lock
docker compose up --build -d
```

Frontend dependencies are declared in `frontend/package.json` and locked in
`package-lock.json`. Add one inside a container, then rebuild so the dev image picks it up:

```bash
docker run --rm -v "$PWD/frontend":/app -w /app node:24-alpine npm install --package-lock-only <package>
docker compose up --build -d frontend
docker compose exec frontend npm run type-check
```

Frontend checks (all run in CI): `docker compose exec frontend npm run lint`, `… npm run test`,
`… npm run check:contrast`. See [frontend/README.md](frontend/README.md). The UI's design
system (purple palette, tokens, components and accessibility rules) is documented in
[docs/design-system.md](docs/design-system.md), and the dev server renders a style guide at
http://localhost:5173/design.

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
workflow in `backend/tests/integration/`.

**End-to-end:** `bash e2e/run.sh` drives Chromium, Firefox, WebKit and phone emulation
against the production stack over HTTPS, all in Docker. See [e2e/README.md](e2e/README.md).
Things automation can't judge, such as screen readers and real phones, are in
[docs/qa-checklist.md](docs/qa-checklist.md).

**CI:** [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on every pull request
and every push to `main`, and can be started by hand from the Actions tab. It uses the same
Docker commands as above, in this order: ruff lint and format check, migrations up to date,
the full test suite against PostgreSQL, a production image build with
`check --deploy --fail-level WARNING`, then the frontend type-check and production build.

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
| `GET` | `/l/{list_code}` | public; the Vue app's list page. Requests that reach Django directly (port 8000 in development) get a `302` to the list's API URL |
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
# {"id":"…","public_code":"X7pKm2Qv8Nw4Rs6A","public_url":"http://localhost:5173/l/X7pKm2Qv8Nw4Rs6A",
#  "title":"Friday Team Bonding","created_at":"…","expires_at":"…","owner_token":"<PRIVATE>"}

# 2. Extract values. CODE / public_url are PUBLIC, so share them. TOKEN is PRIVATE, keep it.
CODE=$(python3 -c 'import json;print(json.load(open("list.json"))["public_code"])')
TOKEN=$(python3 -c 'import json;print(json.load(open("list.json"))["owner_token"])')
#    (or with jq:  CODE=$(jq -r .public_code list.json); TOKEN=$(jq -r .owner_token list.json))

# 3. Add a link (owner only).
curl -s -X POST $BASE/api/v1/lists/$CODE/links/ \
     -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
     -d '{"title": "Interesting Article", "destination_url": "https://example.com/article"}'
# {"id":"<LINK_ID>", …, "short_url":"http://localhost:5173/r/Ab3Kp7Nq2Wz8Lm5R"}
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
  `cleanup_expired` daily at 03:00 UTC, as set in [`backend/docker/crontab`](backend/docker/crontab). Edit
  that file to change the schedule, then restart with `docker compose up -d`. The command
  deletes expired lists in batches of 500 using short transactions, cascading to links and
  redirects, prunes expired rate-limit entries, and reports the counts in
  `docker compose logs cleanup`. It is idempotent, so running it again is harmless. To run
  it immediately: `docker compose exec cleanup python manage.py cleanup_expired`.
* Physical deletion can lag expiry by up to about 24 hours. A run that fails is retried
  the next night. After deletion, the same URLs return `404`.

## Deployment

The production stack bundles an **nginx** TLS proxy ([deploy/nginx/default.conf.template](deploy/nginx/default.conf.template)).
It's the only published service, on ports 80 and 443, and the API is reachable only on
the internal compose network. Its image is built from [frontend/Dockerfile](frontend/Dockerfile)
with the compiled Vue app inside. nginx:

- serves the app for every path except `/api/`, `/r/` and `/healthz`, which go to Django,
  with the same security headers Django sends (HSTS, `Referrer-Policy: no-referrer`,
  `noindex`) plus a Content Security Policy,

- redirects HTTP to HTTPS and serves Let's Encrypt challenges,
- drops requests for unknown hosts and refuses TLS for unknown names,
- buffers request bodies (protecting Gunicorn's sync workers from slow clients) and caps
  them at 32 KB,
- **overwrites** `X-Forwarded-For`, so clients can't spoof their IP to dodge rate limits.

[`deploy/smoke-test.sh`](deploy/smoke-test.sh) verifies all of this end to end and runs in
CI.

1. **Configure:** `cp .env.example .env` and set real values:
   - a long random `DJANGO_SECRET_KEY`,
   - `DJANGO_ALLOWED_HOSTS` and `SERVER_NAME` (your hostname),
   - `PUBLIC_BASE_URL=https://<hostname>`,
   - the database credentials.

   Optionally set `BLOCKED_DESTINATION_HOSTS` to denylist abusive domains. Restarting with
   `up -d` applies it, including to short URLs already shared. If another proxy or load
   balancer sits in front of nginx, raise `DJANGO_NUM_PROXIES` by one for each.
2. **Get a certificate** into `TLS_CERT_DIR` (default `deploy/certs/`, git-ignored) as
   `fullchain.pem` and `privkey.pem`. With Let's Encrypt, issue the first certificate while
   the stack is down, since port 80 must be free:

   ```bash
   docker run --rm -p 80:80 -v /etc/letsencrypt:/etc/letsencrypt certbot/certbot \
     certonly --standalone -d go.example.com
   mkdir -p deploy/certs
   sudo cp -L /etc/letsencrypt/live/go.example.com/{fullchain,privkey}.pem deploy/certs/
   ```

   For renewals, nginx serves `ACME_WEBROOT` at `/.well-known/acme-challenge/`, so they
   can run while the stack is up:
   `certbot renew --webroot -w deploy/acme`. Copy the files again afterwards and reload
   with `docker compose -f compose.prod.yaml exec nginx nginx -s reload`, for example from a
   certbot `--deploy-hook`.
3. **Start** the stack and check it:

   ```bash
   docker compose -f compose.prod.yaml up --build -d
   docker compose -f compose.prod.yaml exec api python manage.py check --deploy
   curl https://go.example.com/healthz        # {"status": "ok"}
   ```

**Internal-only deployment:** uncomment the `allow` / `deny` block in the nginx template
and list your office or VPN ranges. That removes most of the public-abuse risk in
[docs/security.md](docs/security.md).

**Use rootful Docker on the server.** Rootless Docker's default port forwarding replaces
every client's IP with the gateway address, so all clients would share one rate limit. If
you must run rootless, use the `slirp4netns` port driver.

**Background worker (V2).** The `worker` service runs background tasks; from task 7.3 it
fetches the pages behind links (titles, descriptions, icons), and it is the only process that
contacts other sites. `METADATA_FETCH_ENABLED=false` turns fetching off;
`FETCH_BLOCKED_NETWORKS` adds address ranges it must never reach (internal services on public
addresses, such as your company's range). After deploying task 7.3, run
`docker compose -f compose.prod.yaml exec api python manage.py backfill_metadata` once, so
existing links get their details too; `WORKER_REPLICAS`
sets how many tasks run at once (default 2). Check it with
`docker compose -f compose.prod.yaml ps worker` (healthy) and see the queue with
`docker compose -f compose.prod.yaml exec worker python manage.py check_worker`. Two optional
hardening steps, on top of the fetcher's own checks
([docs/v2/14-INFRASTRUCTURE.md](docs/v2/14-INFRASTRUCTURE.md#worker-egress)):

- block the worker's egress to private ranges at the host, e.g.
  `iptables -I DOCKER-USER -s <worker subnet> -d 10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,169.254.0.0/16,100.64.0.0/10 -j DROP`
  (find the subnet with `docker network inspect`);
- give the worker its own compose network containing only `db`, plus the default bridge for
  outgoing traffic, so it can't reach `api` or `nginx`.

**Bringing your own proxy** (Traefik, a cloud load balancer, …): remove the `nginx`
service and publish the API on a private interface, e.g. `127.0.0.1:8000:8000`. Your
proxy must then do what the bundled nginx does: set `X-Forwarded-Proto: https`, overwrite
`X-Forwarded-For` (or set `DJANGO_NUM_PROXIES` to match its chain), and buffer requests.

The production image (`prod` target) has no dev dependencies, runs as a non-root `app`
user, and serves through Gunicorn (`WEB_CONCURRENCY` workers, 30 s timeout, access log to
stdout). Production settings enable the SSL redirect, HSTS, the proxy SSL header, secure
cookies, persistent DB connections with health checks, and `DEBUG=False`.

More detail: [docs/decisions.md](docs/decisions.md) (design decisions and trade-offs) and
[docs/security.md](docs/security.md) (threat model and limitations).
