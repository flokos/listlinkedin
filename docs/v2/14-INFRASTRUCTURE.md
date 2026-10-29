# 14: Infrastructure

V2 keeps V1's Docker-only, single-host Compose deployment: dev `compose.yaml`, prod
`compose.prod.yaml`, nginx in front, PostgreSQL behind. Each addition below names the concrete
workload that needs it (prompt Part 15). There is still no virtualenv and nothing installed on
the host.

## Services

| Service | V1 | V2 change | Why |
|---|---|---|---|
| `db` (postgres:17) | ✓ | none (adds `pg_trgm` via migration) | the single source of truth |
| `migrate` (one-shot) | ✓ | runs with the statement timeout lifted ([06](06-MIGRATION-PLAN.md#schema-and-data-migrations-by-phase)) | migrations before anything starts (V1 pattern) |
| `api` (Gunicorn / runserver) | ✓ | mounts the `media` volume read-write. New settings (auth, sessions, CSRF, email, TASKS) | HTTP |
| **`worker`** | — | **new**: the same image, `python manage.py db_worker` (django-tasks-db), `depends_on: migrate`, `restart: unless-stopped`, media read-write | metadata fetching and image processing. These are slow, external and failure-prone, and must not tie up the 3 sync Gunicorn workers |
| `cleanup` (supercronic) | ✓ | crontab additions ([below](#scheduled-jobs)); mounts `media` read-write (since 2.3) | scheduled maintenance |
| `nginx` (prod) | ✓ | `/media/` location (read-only volume), `/_allauth/` proxied, upload locations with a larger body limit | static, media and TLS |
| `frontend` (dev) | ✓ | Vite proxy also forwards `/_allauth/` and `/media/` | dev parity |
| `mailpit` (dev and e2e only) | — | since task 1.2: in `compose.yaml` (read mail at http://localhost:8025) and in `e2e/compose.e2e.yaml` (tests open emailed links) | email flows can't be tested otherwise. 14 MB image. Not used in production |

New volume: `media` (prod: a named volume or host path, included in backups). Since task 2.3
it is mounted at `/srv/media` in `api` and `cleanup` (read-write) and in `nginx` (read-only). The
prod image creates `/srv/media` owned by the non-root `app` user, so a new named volume is
writable. A host path needs `chown 10001` instead.

### Considered and not added

| Component | Verdict |
|---|---|
| **Redis** | Not needed. Rate limits use the PostgreSQL DatabaseCache with advisory locks (V1, proven exact under concurrency). Sessions use the database backend. The task queue uses PostgreSQL `SKIP LOCKED` (django-tasks-db). Redis would add speed nobody needs, not correctness |
| **Celery / RabbitMQ** | Not needed. One background workload (metadata) at low volume. Celery needs a broker plus worker and beat processes. Django 6.0's Tasks API is the forward-compatible standard [R2], and the django-tasks backport runs it on our Django 5.2 [R4][R5] |
| Elasticsearch / OpenSearch | Not needed. PostgreSQL FTS plus `pg_trgm` cover title and description search over public lists [R11] |
| S3 / object storage | Not needed on one host. If the deployment becomes multi-host, switch to `django-storages` behind the same `MEDIA_*` settings (an ADR at that time) |
| Kubernetes, extra databases, event stores | No requirement (prompt 1.3) |

## Background worker

- Library: `django-tasks` 0.12.0 (backport of Django 6.0's `django.tasks`, supports Django
  5.2, PyPI "Production/Stable") [R4], with **`django-tasks-db`** 0.13.0 (the ORM/PostgreSQL
  backend, "Beta", supports Django 5.2/6.0, worker command `db_worker`, results pruned with
  `prune_db_task_results`, uses `SKIP LOCKED`) [R5]. Both are pinned exactly in `uv.lock`, as
  the project recommends for production. On upgrading to Django 6.2 LTS, `django.tasks` is
  built in and only the database backend package remains.
- Configuration: `TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend",
  "QUEUES": ["default"]}}`. Tests use `ImmediateBackend`.
- Enqueue only through `transaction.on_commit`.
- Tasks are idempotent and guarded: the worker re-reads the link and does nothing if it was
  deleted or its URL changed since the task was enqueued, so results can't land on the wrong
  URL ([ADR-008](adr/ADR-008-background-metadata-extraction.md)).
- **Fallback if django-tasks-db proves unsuitable** in task 7.1: a ~100-line
  `metadata_fetch_job` table claimed with `SELECT … FOR UPDATE SKIP LOCKED` by a management
  command loop. Same container, same semantics.

## Worker egress

The worker is the only process that talks to arbitrary hosts. In production, also restrict
its egress at the host (defence in depth on top of the fetcher's pinning, [13](13-SECURITY.md#ssrf-safe-fetcher)):

```bash
# Example: block private ranges and the metadata endpoint for the worker's bridge network.
iptables -I DOCKER-USER -s <worker_subnet> -d 10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,169.254.0.0/16,100.64.0.0/10 -j DROP
```

The worker still reaches `db` on the internal compose network. Give it its own network that
contains only `db`, plus the default bridge for egress. This is optional and is documented in
the deployment README in task 7.1.

## Email

V2 sends email: verification, password reset and collaborator notices. Configuration is
`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` and
`DEFAULT_FROM_EMAIL`. Dev and e2e send to Mailpit. Production uses any SMTP relay. Outside
compose, Django's console backend is the base-settings default. The e2e stack also sets
`AUTH_RATE_LIMITS=off`, because every browser there shares one client IP. Production keeps
allauth's limits. It also sets `LEGACY_LIST_CREATION=on`, so specs can seed edit-link lists.

## Environment variables (new)

| Variable | Used by | Default (dev) |
|---|---|---|
| `DJANGO_EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | api | console backend in development, SMTP in production (since task 1.1) |
| `LEGACY_LIST_CREATION` | api | `off`: `POST /api/v1/lists/` answers 410. `on` only in backend tests and the e2e stack, which still seed legacy lists (since task 1.4; removed in 9.6) |
| `MEDIA_ROOT` | api, cleanup, worker | `/srv/media` (since task 2.3) |
| `DB_STATEMENT_TIMEOUT`, `DB_LOCK_TIMEOUT` | api / migrate (production) | api 20s and 5s; `migrate` runs with a statement timeout of 0 (since task 1.1) |
| `METADATA_FETCH_ENABLED` | worker | `true` (`false` disables fetching, for locked-down deployments) |
| `SENTRY_DSN` (optional) | api, worker | empty (disabled) |
| `THROTTLE_*` (extended) | api | V1 defaults + new scopes ([13](13-SECURITY.md#rate-limits)); `THROTTLE_ACCOUNT` 300/hour since task 1.1; `THROTTLE_MEMBER_ADD` 60/hour per user since task 1.5; `THROTTLE_UPLOAD` 120/hour per user since task 2.3 |

## Scheduled jobs

These run under supercronic from `backend/docker/crontab`.

| Schedule (UTC) | Command | Since |
|---|---|---|
| daily 03:00 | `cleanup_expired`: expired lists (sets `parent_deleted_at` on their branches first), throttle cache | V1, extended |
| daily 03:20 | `clearsessions` | V2 |
| daily 03:30 | `prune_db_task_results` (keep 7 days) | V2 |
| weekly Sun 04:00 | `cleanup_media`: delete files referenced by no row and no revision snapshot, older than 7 days | 2.3 (rows: list images, link icons including tombstones; snapshots join in 3.1, fetched icons in 7.3) |

## Backups

V1 had none documented. V2 holds account data and permanent lists, so backups become required:

- Daily `pg_dump -Fc` from the `db` container to a host path outside the volume, kept 14 days,
  with a restore tested monthly.
- `media` volume: daily `rsync`/`tar`. Files are content-addressed and immutable, so it's
  incremental by nature.
- Optional: WAL archiving for point-in-time recovery, if the host supports it.

## Health checks and observability

- `/healthz` (V1, DB round-trip). The worker gets a compose healthcheck: a management command
  that exits non-zero if the oldest ready task is older than 10 minutes or the worker heartbeat
  file is stale.
- **Structured logging:** keep stdout logging and add a JSON formatter in production, plus a
  request-id middleware (`X-Request-ID` set by nginx, echoed back and attached to log
  records), so an api log line and the task it enqueued can be correlated.
- **Merge diagnostics:** every apply logs `{branch_id, fingerprint, decisions_count, outcome,
  error_code, duration_ms}`. Failures keep the request's fingerprint and the current one.
  `SyncRecord` keeps the successful ones.
- **Background task visibility:** the queue depth and the age of the oldest ready task, from
  `manage.py task_stats`, are printed in `cleanup` logs daily and by the healthcheck.
- **Error reporting:** optional `sentry-sdk` when `SENTRY_DSN` is set. Not a hard dependency.
  Without it, errors go to logs, as in V1.
- No Prometheus or Grafana stack (prompt 15.3).

## Performance targets (initial)

| Operation | Target (p95, single host, 3 Gunicorn workers) |
|---|---|
| List page API (detail + 100 links) | < 150 ms, ≤ 4 queries |
| Group workspace (group + 30 visible lists) | < 200 ms, ≤ 5 queries |
| `/r/{code}` redirect | < 50 ms, 1–2 queries |
| Directory search (100k public lists) | < 300 ms |
| Sync preview (100 links), postponed (ADR-015) | < 200 ms (3 snapshot reads + an in-memory plan) |
| Sync apply (100 links), postponed (ADR-015) | < 500 ms |
| Metadata fetch | asynchronous. 90 % of fetches finish within 15 s of creation |

N+1 prevention: annotated querysets (V1's short-code subquery pattern), `select_related` and
`prefetch_related` on group entries, and a `django_assert_max_num_queries` test per endpoint
([15](15-TEST-STRATEGY.md)). No cache layer is added. Add one only for a measured hotspot.

## Django and dependency versions

Stay on **Django 5.2 LTS** (extended support until April 2028) through V2 development and
launch. Plan the upgrade to **6.2 LTS** (due April 2027) as a separate post-launch project
([ADR-014](adr/ADR-014-django-version.md), [R3]). DRF 3.16 → 3.18 (3.18.3 current [R24]) is a
small dependency PR in phase 1. New Python dependencies: `django-allauth`, `django-tasks`,
`django-tasks-db`, `Pillow`, `urllib3`, and optionally `sentry-sdk`. New dev dependency:
`hypothesis` ([15](15-TEST-STRATEGY.md#unit-tests-pure-domain)).
