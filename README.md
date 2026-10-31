# listlinkedin: lists of links, with short URLs that keep working

listlinkedin is a web app for collecting links into **lists** and sharing them. Each link gets
a short URL (`/r/{code}`) that keeps working when the link's destination changes. Each list
has a stable address (`/l/{code}`).

- **Accounts** with an email address and a password. Sign-up, email verification and
  password resets use [django-allauth](https://docs.allauth.org/)'s headless API. Deleting an
  account starts a 30-day grace period. Signing in again within it restores everything.
- **Lists** are private, unlisted (anyone with the address) or public (listed on Explore).
  They are permanent unless you set an expiry date. An owner can add **editors** and
  **viewers** by email.
- **Links** show as tiles or rows. You can reorder them by drag, or with ⋮ Move items that
  work by keyboard. Titles, descriptions and icons are fetched in the background and never
  overwrite what you typed.
- **History:** every change writes an immutable revision, which you can view, compare and
  restore. **Make a copy** forks a list, if its owner allows copies.
- **Groups** collect lists into a workspace with a sidebar. A group never grants access to
  its lists: people see only the lists they could open anyway.
- **Explore** searches public lists and groups by text and tags.
- **Reports:** anyone can report a list or group, and the report is emailed to the operator.
  The operator acts with management commands ([moderation](docs/deployment.md#moderation)).

Version 1, the anonymous 30-day lists with an edit link, is described in
[docs/v1/](docs/v1/README.md) and kept on the `release/v1` branch. Since v2.1.0 every list
belongs to an account: V1's API and edit links are gone (V1 was never deployed).

Everything runs in Docker. You need Docker Engine or Desktop with Compose, Git and an editor.
You don't need a virtualenv or host Python or Node.

## Quick start (development)

```bash
docker compose up --build -d            # db, migrations, api, worker, cleanup, mailpit, frontend
open http://localhost:5173/             # the app (Vite dev server, hot reload)
open http://localhost:8025/             # Mailpit: every email the app sends lands here
open http://localhost:8000/api/docs/    # API reference (Swagger UI)
docker compose logs -f api worker
docker compose down                     # stop (add -v to delete the database and images)
```

This works from a clean checkout. `compose.yaml` has development defaults, so you don't need
a `.env`. To get an account:

1. Choose **Sign up** in the app.
2. Open the confirmation email in Mailpit and click its link.

Development mail never leaves your machine.

To run the production stack on your machine (nginx with TLS, Gunicorn, the built app), use
`bash e2e/run.sh` or `bash deploy/smoke-test.sh`. Both start it in an isolated compose
project with a throwaway certificate, test it, and remove it. For a real server, read
[docs/deployment.md](docs/deployment.md).

## Architecture

A modular monolith: one Django project with one app per domain, a Vue single-page app, and
PostgreSQL as the only stateful service. It also holds the task queue and the rate limits.

```text
backend/                Django 5.2 + Django REST Framework (its own Docker build context)
  config/                 settings (base, development, production), urls, middleware, logging
  apps/sharing/           Lists and Links, memberships, visibility, the policy module, moderation
  apps/shortener/         short codes and /r/{code} (visibility checked through sharing)
  apps/accounts/          the User, sessions, /api/v2/session/ and /api/v2/me/, allauth glue
  apps/groups/            Groups and their lists
  apps/versioning/        revisions, snapshots and diffs (domain/ has no Django imports)
  apps/metadata/          the task queue, the SSRF-safe fetcher, image processing
  common/                 framework-free domain errors
  templates/account/      the account emails' wording
frontend/               Vue 3 + Vuetify 4 + TypeScript; its Dockerfile also builds nginx
deploy/                 nginx config, smoke test, performance run, backup, restore, autoheal
e2e/                    Playwright tests against the production stack
docs/                   deployment guide, design system, QA checklist; v2/ specs and ADRs
compose.yaml            development stack   ·   compose.prod.yaml   production stack
```

Requests go **view** (HTTP only) → **service** (transactions, row locks, rules) or
**selector** (reads) → the ORM. Every permission decision goes through the policy module.
List queries filter by visibility in SQL. One app never writes another app's tables. The
binding rules are in [CLAUDE.md](CLAUDE.md) and the design is in [docs/v2/](docs/v2/README.md):

- [architecture](docs/v2/03-ARCHITECTURE.md)
- [domain model](docs/v2/04-DOMAIN-MODEL.md)
- [database](docs/v2/05-DATABASE-DESIGN.md)
- [authorization](docs/v2/12-AUTHORIZATION.md)
- [security](docs/v2/13-SECURITY.md)
- [ADRs](docs/v2/adr/README.md)

| Service | Role |
|---|---|
| `db` | PostgreSQL 17. Data, the task queue, sessions and rate limits |
| `migrate` | Runs once: `migrate` and `createcachetable`. Everything else waits for it to succeed |
| `api` | Django: `runserver` in development, Gunicorn in production. Health check `/healthz` |
| `worker` | Background tasks from the PostgreSQL queue (`db_worker`): fetching link details and processing images. The only process that contacts other sites. Health check `check_worker` |
| `cleanup` | [supercronic](https://github.com/aptible/supercronic) running [backend/docker/crontab](backend/docker/crontab): expired lists, sessions, stuck tasks, erased accounts, unused images |
| `frontend` | Development only: the Vite dev server. It proxies the API, so the app sees a single origin |
| `nginx` | Production only: TLS, the built app, `/media/`, and a proxy to the API |
| `mailpit` | Development and e2e only: catches outgoing mail |

There is no Redis, Celery or other broker. Background work uses a queue table in PostgreSQL
([ADR-008](docs/v2/adr/ADR-008-background-metadata-extraction.md)).

## Development commands (all inside Docker)

```bash
docker compose exec api python manage.py migrate
docker compose exec api python manage.py makemigrations
docker compose run --rm api python manage.py makemigrations --check --dry-run
docker compose run --rm --no-deps api sh -c "ruff check . && ruff format --check ."
docker compose exec frontend sh -c "npm run lint && npm run type-check && npm run format:check"
docker compose exec frontend sh -c "npm run test && npm run check:contrast"
```

**Dependencies:**

- Python dependencies are declared in `backend/pyproject.toml` and locked in `uv.lock`.
- Frontend dependencies are declared in `frontend/package.json` and locked in
  `package-lock.json`.

Change them inside a container, then rebuild:

```bash
docker run --rm -v "$PWD/backend":/app -w /app ghcr.io/astral-sh/uv:0.9.5-python3.14-bookworm-slim uv lock
docker run --rm -v "$PWD/frontend":/app -w /app node:26-alpine npm install --package-lock-only <package>
docker compose up --build -d
```

**Frontend:**

- [frontend/README.md](frontend/README.md) covers the frontend's structure.
- The design system (palette, tokens, components, accessibility rules) is in
  [docs/design-system.md](docs/design-system.md).
- The dev server renders a style guide at http://localhost:5173/design.

> Dev containers run as the image's root user, so files created through the bind mount
> (new migrations, for example) belong to you under rootless Docker. With rootful Docker,
> add `--user "$(id -u):$(id -g)"` to `docker compose run` and `exec` commands that write
> files.

## Testing

```bash
docker compose run --rm api pytest                 # backend, against a real PostgreSQL
docker compose exec frontend npm run test          # frontend unit tests (Vitest)
bash e2e/run.sh                                    # browsers against the production stack
bash e2e/run.sh --project=chromium a11y.spec       # one browser, one spec
bash deploy/smoke-test.sh                          # the production stack's HTTP behaviour
```

- **Backend tests** include real concurrency tests and query budgets per endpoint.
- **End-to-end tests** run in Chromium, Firefox, WebKit and two phone emulations, with axe
  on every page in light and dark ([e2e/README.md](e2e/README.md)).
- **Manual checks** cover what automation can't judge, like screen readers and real phones:
  [docs/qa-checklist.md](docs/qa-checklist.md).
- **The test levels** are described in
  [docs/v2/15-TEST-STRATEGY.md](docs/v2/15-TEST-STRATEGY.md).

**CI** ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs three jobs on every pull
request:

- `checks`: lint, formatting, migrations, the backend and frontend tests, the dependency
  audit and the production build.
- `proxy`: the smoke test.
- `e2e`: the end-to-end tests.

## API

- **Interactive reference:** `/api/docs/` (Swagger UI). The OpenAPI schema is at
  `/api/schema/`. In development: http://localhost:8000/api/docs/.
- **Design and conventions:** [docs/v2/09-API-DESIGN.md](docs/v2/09-API-DESIGN.md):
  resources, errors, `If-Match` preconditions, pagination and rate limits.

| Path | What |
|---|---|
| `/api/v2/` | The API the app uses. Session cookie plus CSRF; anonymous visitors can read what they're allowed to see |
| `/_allauth/browser/v1/` | Sign-up, sign-in, email verification, password reset (allauth headless) |
| `/r/{code}` | A link's short URL: `302` to its current destination, if you may see its list |
| `/l/{code}` | A list's page in the app |
| `/healthz` | `200 {"status": "ok"}`, or `503` when the database is unreachable |

## Deployment

[docs/deployment.md](docs/deployment.md) covers:

- the server and every environment variable;
- TLS, the first deploy and upgrades;
- the worker, media and email;
- backups and restores;
- monitoring;
- the operator's moderation commands.

## Documentation

| | |
|---|---|
| [docs/deployment.md](docs/deployment.md) | Running it in production, operating it |
| [docs/v2/](docs/v2/README.md) | The V2 specs, ADRs, roadmap, security review |
| [docs/design-system.md](docs/design-system.md) | The UI's design system |
| [docs/qa-checklist.md](docs/qa-checklist.md) | Manual accessibility and device checks |
| [docs/v1/](docs/v1/README.md) | Version 1: its README, decisions and threat model |
| [CLAUDE.md](CLAUDE.md) | Working rules for contributors and coding agents |
