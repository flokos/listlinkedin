# 01: Version 1 audit

What V1 actually is at `main` = `fb5f901` (2026-10-28). Everything here is **[Observed]** unless
labelled otherwise. The planning prompt describes an *intended* V1, and
[Discrepancies](#discrepancies-between-the-prompts-intended-v1-and-the-real-v1) lists where the
two differ.

## Summary

V1 is a small, carefully hardened, Docker-only modular monolith. It has a Django 5.2 + DRF
API, a Vue 3 + Vuetify 4 SPA, PostgreSQL 17, an nginx TLS proxy and a supercronic cleanup job.
There are no user accounts. A list is managed with a 256-bit owner token that the browser keeps
in `localStorage` and the user keeps as an "edit link". Lists expire 30 days after creation.
Code quality is high: invariants are enforced in the database, every write runs under a row
lock, and races are tested. Most of it can be reused as is. The parts V2 must change are the
ownership model, the fixed lifetime, the Link fields and ordering, and the absence of revisions,
groups and a worker.

**Baseline verified on 2026-10-28** in an isolated compose project (`-p listlinkedin-v2check`):

| Check | Result |
|---|---|
| `ruff check` / `ruff format --check` | pass (43 files) |
| `makemigrations --check` | no changes |
| `pytest` (PostgreSQL 17) | **129 passed** (87 test functions, some parametrized) |
| Frontend lint, format, type-check, Vitest, contrast | all pass |
| CI on `fb5f901` (checks, proxy smoke test, e2e in 5 browser projects) | success (GitHub Actions, push to `main`, 2026-10-28) [R31] |

## Repository and Git

| Item | Finding |
|---|---|
| Hosting | GitHub `flokos/listlinkedin`, **public**, default branch `main`. The planner's account is ADMIN |
| Branches | `main` (= `origin/main`), plus remote `test/e2e` and a local `feat/frontend-app` whose upstream is gone. Both are merged and left untouched |
| Protection | None before V2 planning: no branch protection, no rulesets |
| Worktrees, stash, hooks | One worktree, empty stash, no client hooks |
| History | 7 PRs, all into `main` (#3–#5 were superseded and closed) |
| Uncommitted work | Only the untracked V2 prompt, committed on `v2` by this planning run |

## Backend

### Stack (from `backend/pyproject.toml`, `uv.lock`)

Python 3.13, Django **5.2.18** (LTS), DRF **3.16.1** (pinned `<3.17`), drf-spectacular 0.30.0,
psycopg 3.3.6, gunicorn 26.2, idna 3.20. Dev: pytest 9.1, pytest-django 4.14, ruff. Packages
install into the image's system Python with `uv sync --locked`. There is no virtualenv.

### Structure

```text
backend/
  config/settings/{base,development,production}.py, urls.py, middleware.py, wsgi.py
  apps/sharing/    models, domain, tokens, services, selectors, permissions, serializers, views, urls,
                   exceptions, management/commands/cleanup_expired.py, tests/
  apps/shortener/  generators, models, services, views, tests/
  tests/integration/test_workflow.py
  conftest.py, docker/crontab, Dockerfile (dev + prod targets)
```

### Models and schema (migrations `sharing/0001`, `shortener/0001`, one each)

| Model | Fields | Constraints |
|---|---|---|
| `SharedList` | `id` UUIDv4 PK, `public_code` char(16), `owner_token_hash` char(64) SHA-256 hex, `title` ≤255, `created_at`, `updated_at`, `expires_at` (indexed) | `sharing_list_public_code_uniq` |
| `SharedLink` | `id` UUIDv4 PK, `shared_list` FK CASCADE, `destination_url` TEXT (normalized), `title` NULL ≤255, `created_at`, `updated_at` | `sharing_link_destination_per_list_uniq` (`shared_list`, `destination_url`) |
| `ShortRedirect` | `id` UUIDv4 PK, `code` char(16), `link` FK CASCADE, `is_active`, `created_at` | `shortener_redirect_code_uniq` |

Not installed: `django.contrib.auth`, `contenttypes`, `sessions`, `admin`, CSRF middleware.
**So no auth tables exist in any V1 database.** That matters for the custom user model
([ADR-007](adr/ADR-007-authentication-and-ownership-migration.md)). A DatabaseCache table
`rate_limit_cache` is created by `createcachetable`, not by a migration.

### API (`/api/v1/`, APIViews)

| Method | Path | Access |
|---|---|---|
| POST | `/api/v1/lists/` | public, throttled 30/h/IP; returns `owner_token` once |
| GET/PATCH/DELETE | `/api/v1/lists/{code}/` | GET public; PATCH (title) and DELETE need the owner token |
| POST | `/api/v1/lists/{code}/rotate-token/` | owner |
| GET/POST | `/api/v1/lists/{code}/links/` | GET public, paginated (20, max 100, newest first); POST owner |
| PATCH/DELETE | `/api/v1/lists/{code}/links/{uuid}/` | owner |
| GET | `/r/{code}` | 302 to the current destination, `no-store`, `no-referrer`; 404 unknown/deleted, 410 expired/inactive/blocked |
| GET | `/l/{code}` | Django: 302 to the API URL. Behind nginx the SPA serves it |
| GET | `/healthz` | DB round-trip, answered before host checks |
| GET | `/api/schema/`, `/api/docs/`, `/api/redoc/` | OpenAPI |

### Authentication and authorization

- `OwnerTokenAuthentication` turns `Authorization: Bearer <token>` into `request.auth`, with
  no user. `IsListOwnerOrReadOnly` compares `sha256(token)` with the list's hash in constant
  time. Reads are public.
- `_lock_active_list` re-reads the list `SELECT … FOR UPDATE` in every write. It re-checks
  expiry and rejects with 403 if the token was rotated mid-request.
- `WriteRateThrottle`: DRF `ScopedRateThrottle` on unsafe methods only. It is serialized per
  (scope, IP) with `pg_advisory_xact_lock` and stored in the PostgreSQL DatabaseCache.

### Business logic placement

- `domain.py`: lifetime (30 days), `MAX_LINKS_PER_LIST = 100`, `MAX_URL_LENGTH = 2048` bytes,
  minimal URL normalization (RFC 3986 scheme-based equivalences plus IDNA2008/UTS 46 hosts), and
  the destination host policy (own hosts plus `BLOCKED_DESTINATION_HOSTS`). It imports Django
  settings and `ValidationError`, so it is **not framework-free**.
- `services.py`: every write, inside `transaction.atomic` and the row lock. It raises DRF
  exceptions directly. This was a deliberate V1 decision (docs/decisions.md).
- `selectors.py`: reads (404 vs 410, links annotated with their active short code).
- `shortener.services.create_with_unique_code()`: random code, insert in a savepoint, retry
  only when the named unique constraint is violated (`diag.constraint_name`), 5 attempts. It is
  generic and reusable for group codes.

### Identifiers

16-character Base64URL codes from `secrets.token_bytes(12)` (96 bits) for lists and redirects.
UUIDv4 primary keys. Owner tokens: `secrets.token_urlsafe(32)`, stored as SHA-256.

### Background jobs

`cleanup` container: supercronic runs `cleanup_expired` at 03:00 UTC. It deletes in batches of
500, prunes the throttle cache, and is single-instance through `pg_try_advisory_lock`. There is
no task queue, no Redis and no Celery.

### Configuration

Everything comes from environment variables (`.env.example`). `PUBLIC_BASE_URL` and the
denylist are validated at startup. Production adds HSTS, SSL redirect, `NUM_PROXIES`,
`CONN_MAX_AGE`, `lock_timeout=5s` and `statement_timeout=20s`, and silences `security.W003`
(no CSRF middleware) and `W021`.

## Frontend

| Aspect | Finding |
|---|---|
| Stack | Vue 3.5, Vuetify 4.3, vue-router 5, Vite 8, TypeScript 6, Vitest 5, ESLint 10, Prettier. `@mdi/js` icons, `qrcode`, self-hosted Inter |
| Routing | `/` Home (create), `/lists` Saved lists, `/about`, `/l/:code` list, `/l/:code/manage#t=` claim, `/design` (dev only), 404. Focus moves to `<h1>` on navigation, titles come from the route, and stale chunks are reloaded |
| State | No store library. Module-level `reactive` singletons in composables: `useOwnedLists` (localStorage `ll:owned-lists`, cross-tab sync), `useListPage` (load, cache, owner actions) |
| API | `api.ts`: a typed `fetch` client. `ApiError` exposes DRF field errors, `detail` and `Retry-After`. `NetworkError`. `credentials: 'omit'` (no cookies) |
| Ownership UX | Token saved in localStorage plus an "edit link" `/l/{code}/manage#t={token}` that is stripped from the address bar. Rotate ("Replace edit link"), forget, JSON backup and restore |
| List page | `ListView.vue` (619 lines): header (rename, expiry chip, count, Share, ⋮ owner menu), add-link card with `LinkLimitMeter`, client-side search (`/` shortcut) and sort (Newest/A–Z), `LinkCard` rows (`DomainAvatar`, title, URL, copy short link, open, ⋮ Edit/Delete), dialogs |
| Shared components | `StatePanel`, `ConfirmDialog` (type-to-confirm), `CopyField`, `ShareDialog` (QR, native share), `EditLinkReveal`, `ClaimTokenDialog`, `BackupCard`, `ExpiryChip`, `LinkForm`, `RouteAnnouncer`, `RouteProgress`, `ThemeMenu`, `AppHeader`, `AppNavDrawer` (temporary drawer on mobile), `AppFooter` |
| Design system | Purple tokens (`design/tokens.ts`), theme roles, MD3 type scale, motion respects reduced motion, and `npm run check:contrast` enforces WCAG 2.2 AA in CI ([docs/design-system.md](../design-system.md)) |
| Responsive | Content column 880px, app bar on desktop, modal drawer on mobile, phone e2e projects |
| Errors | Status-specific copy (`describeStatus`), states for not found, expired, error, offline and 429 |

Copy that assumes V1 rules and must change with V2: "Gone after 30 days", "Free, no sign-up.
Lists expire after 30 days." (`CreateListForm`), the footer, the About page, and the expired
state text.

## Infrastructure

| Item | Finding |
|---|---|
| Compose (dev) | `db` (postgres:17, healthcheck), `migrate` (one-shot migrate + createcachetable), `api` (runserver, bind mount), `cleanup`, `frontend` (Vite dev server, proxies `/api/` and `/r/`) |
| Compose (prod) | The same backend services on the `prod` image (Gunicorn, non-root), plus `nginx` (the only published service) with the built SPA baked in |
| nginx | TLS 1.2/1.3, unknown hosts get 444, `client_max_body_size 32k`, overwrites `X-Forwarded-For`, CSP `default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'`, `noindex`, immutable `/assets/` |
| CI | `.github/workflows/ci.yml`: `checks` (ruff, migrations, pytest, prod image deploy check, frontend lint/format/test/contrast/build), `proxy` (`deploy/smoke-test.sh`), `e2e` (`e2e/run.sh`). Triggers: PRs to any branch and pushes to `main` |
| Secrets | Environment only. `.env` and TLS material are git-ignored |
| Logging and monitoring | Plain-text logs to stdout, Gunicorn access log, `/healthz`. No metrics or error tracker |
| Static and media | Static files are the SPA in nginx. There is **no media storage**, since V1 has no uploads |
| Developer tooling | `.mcp.json` (Playwright MCP), `.vscode/extensions.json` |

## Tests

| Suite | Size | Covers |
|---|---|---|
| `apps/sharing/tests` | 75 functions (`test_security` 35, `test_links` 14, `test_lists` 12, `test_expiration` 11, `test_domain` 3) | CRUD, ownership, rotation, throttling (with real concurrency), normalization, denylist, expiry, cleanup, OpenAPI auth marking, deploy checks |
| `apps/shortener/tests` | 11 | Code format, 302/404/410, simulated collisions, uniqueness |
| `tests/integration` | 1 | The full workflow over HTTP |
| Frontend unit (Vitest) | 33 tests in 7 files | `api.ts`, `useOwnedLists`, `useEditLink`, `LinkForm`, url/time/backup utils |
| E2E (Playwright) | 34 tests in 12 specs × 5 projects (chromium, firefox, webkit, mobile-safari, mobile-chrome) | create, links, ownership, share, navigation, keyboard, states (mocked 429/5xx/offline), a11y (axe), limits, content |
| Manual | [docs/qa-checklist.md](../qa-checklist.md) | Screen readers, real devices, zoom, forced colours |

Gaps: no coverage measurement on either side, no load test, and no test of multiple
application instances beyond the concurrency tests. The V2 regression checklist in
[15-TEST-STRATEGY.md](15-TEST-STRATEGY.md#v1-regression-checklist) lists which of these tests
must keep passing.

## Discrepancies between the prompt's intended V1 and the real V1

| # | Prompt says / implies | Reality | Consequence for V2 |
|---|---|---|---|
| 1 | V1 uses DRF ViewSets | **APIViews** (`views.py`) | V2 adopts ViewSets for `/api/v2/` ([ADR-010](adr/ADR-010-viewsets-and-api-v2.md)) |
| 2 | Entities `List` and `Link` | `SharedList`, `SharedLink` | Names kept, glossary maps them ([ADR-001](adr/ADR-001-preserve-list-and-link.md)) |
| 3 | Business logic separated from API concerns | Mostly true, but services raise DRF exceptions and `domain.py` imports settings | New domain core is framework-free; existing code migrates when touched |
| 4 | A ShortURL entity with several target types | `ShortRedirect` maps codes to links only; list codes are a column | Kept as is, groups get a column too ([ADR-006](adr/ADR-006-url-shortening-strategy.md)) |
| 5 | "Temporary collections retained for one month" | 30 days, immutable, enforced at the request level, purged daily | Expiry becomes optional; legacy lists keep theirs |
| 6 | Creator-controlled management links | Owner token, edit link with the token in the URL fragment, rotation, backup file | Legacy principal and claim flow ([06](06-MIGRATION-PLAN.md#ownership-transition)) |
| 7 | (not mentioned) | 100-link cap, 16 KB body cap, URL ≤2048 bytes | Kept; uploads get their own size limits |
| 8 | (not mentioned) | Links ordered newest-first by `created_at`; no position | Positions are backfilled to preserve today's order |

## Technical debt found

- `docs/decisions.md` still says "Project at repo root, not `backend/`", which has been wrong
  since `c35e627`. `docs/security.md` says "2048 characters" where the code counts bytes.
  Both are minor and should be fixed on `main` as V1 doc fixes.
- `verifyOwnership` in the frontend uses an empty `PATCH`, which bumps `updated_at`. This is
  documented. V2's claim endpoint makes it unnecessary.
- DRF is pinned below 3.17, while 3.18.3 is current [R24]. drf-spectacular's classifiers stop
  at Django 5.1 but it works on 5.2 (CI passes). Upgrading belongs in a dedicated PR.
- `ListView.vue` (619 lines) and `api.ts` will not scale to V2 as single modules
  ([10](10-FRONTEND-ARCHITECTURE.md)).
- Environment note, not repository debt: the planner's local dev stack had a crash-looping
  `api` container created before the `backend/` split. `docker compose up --build -d`
  recreates it.

## Reuse opportunities

| Reuse as is | Extend |
|---|---|
| `create_with_unique_code`, `generate_short_code` (group codes) | `normalize_destination_url`, `is_blocked_destination`, which also gate metadata fetching |
| `_lock_active_list` pattern (the lock-then-recheck write path) | `services.py` (owner and visibility, revisions) |
| `WriteRateThrottle` + DatabaseCache (no Redis) | `cleanup_expired` (purge tasks, sessions, task results) |
| `/healthz`, request-size middleware, `Gone`, `noindex` | Request-size middleware (per-path limits for uploads) |
| supercronic and the one-shot `migrate` service | `IsListOwnerOrReadOnly`, which becomes the V2 policy |
| Frontend: `StatePanel`, `ConfirmDialog`, `CopyField`, `ShareDialog`, `DomainAvatar`, `ExpiryChip`, `RouteAnnouncer`, `useNotify`, `useClipboard`, the design tokens, the contrast script, the e2e fixtures | `LinkCard` (list view), `LinkForm` (description, icon), `AppNavDrawer` (group sidebar), `api.ts` (split by resource), `useOwnedLists` (legacy section and claim) |

## Compatibility risks

1. **Shared URLs in the wild:** `/l/{code}`, `/r/{code}` and `/l/{code}/manage#t=` must keep
   working. Codes never change.
2. **External API users** of `/api/v1/` (the README documents curl usage).
3. **Edit links in users' backup files** (format `version: 1`) must stay restorable until the
   last legacy list expires.
4. **Visible behaviour changes** (manual order, accounts, optional expiry) need copy and UX
   changes, not silent switches.
5. **CSP and `noindex`** are strict. Fetched images and any indexing decision must work with them.
