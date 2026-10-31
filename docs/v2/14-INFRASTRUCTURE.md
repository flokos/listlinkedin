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
| **`worker`** | — | **new** (task 7.1): the same image, `python manage.py db_worker` (django-tasks-db), `depends_on: migrate`, `restart: unless-stopped`, media read-write, healthcheck `check_worker`, `stop_grace_period: 30s`; two replicas in production (`WORKER_REPLICAS`), one in development (auto-reloading) | metadata fetching and image processing. These are slow, external and failure-prone, and must not tie up the 3 sync Gunicorn workers |
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
  "QUEUES": ["default"]}}`, everywhere including tests: the immediate backend can't defer a
  task, which retries need, so tests run queued tasks with `db_worker --batch` in tests that
  really commit (`apps/metadata/tests/test_tasks.py`).
- Enqueue only through `apps/metadata/tasks.enqueue_on_commit` (`transaction.on_commit`: the
  library inserts the row at once). Temporary failures retry through `retry_or_give_up`
  (3 attempts, pauses of 30 s and 5 min). Since task 7.1, with what the library does and
  doesn't do recorded in [ADR-008](adr/ADR-008-background-metadata-extraction.md#verified-in-task-71).
- **Hard time limit** (since 7.2): tasks are declared with `@background_task`; one running
  past 120 s ends the worker process (exit 70), compose restarts it and the task runs again.
- **Tasks left running by a dead worker** (the library never recovers them) are run again by
  `recover_stuck_tasks` every 5 minutes, or failed after 3 runs. A task must finish well within
  `TASK_STALE_AFTER` (10 minutes).
- Tasks are idempotent and guarded: the worker re-reads the link and does nothing if it was
  deleted or its URL changed since the task was enqueued, so results can't land on the wrong
  URL ([ADR-008](adr/ADR-008-background-metadata-extraction.md)).
- **Swappable runner:** one enqueue point (`metadata/tasks.py`), thin task wrappers over plain
  functions, and all state in PostgreSQL, so a later move to Celery is a contained change
  ([ADR-008](adr/ADR-008-background-metadata-extraction.md#moving-to-celery-later)).
- **Fallback if django-tasks-db proves unsuitable:** a ~100-line `metadata_fetch_job` table
  claimed with `SELECT … FOR UPDATE SKIP LOCKED` by a management command loop. Not needed:
  task 7.1 adopted the library.

## Worker egress

The worker is the only process that talks to arbitrary hosts. In production, also restrict
its egress at the host (defence in depth on top of the fetcher's pinning, [13](13-SECURITY.md#ssrf-safe-fetcher)):

```bash
# Example: block private ranges and the metadata endpoint for the worker's bridge network.
iptables -I DOCKER-USER -s <worker_subnet> -d 10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,169.254.0.0/16,100.64.0.0/10 -j DROP
```

The worker still reaches `db` on the internal compose network. Give it its own network that
contains only `db`, plus the default bridge for egress. This is optional;
[docs/deployment.md](../deployment.md#worker) describes both steps (since task 7.1; the
README's deployment section until task 9.4).

## Email

V2 sends email: verification, password reset and collaborator notices. Configuration is
`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` and
`DEFAULT_FROM_EMAIL`. Dev and e2e send to Mailpit. Production uses any SMTP relay. Outside
compose, Django's console backend is the base-settings default. The e2e stack also sets
`AUTH_RATE_LIMITS=off`, because every browser there shares one client IP. Production keeps
allauth's limits. (Until v2.1.0 it also set `LEGACY_LIST_CREATION=on`, so specs could seed
edit-link lists.)

Since task 9.0, mail is sent with `EMAIL_TIMEOUT` (10 s by default), so a relay that hangs no
longer holds a Gunicorn worker until its own 30 s timeout. Reports of abuse go to
`MODERATION_EMAIL` ([13](13-SECURITY.md#moderation)); the e2e stack sets it to a Mailpit
address.

## Environment variables (new)

| Variable | Used by | Default (dev) |
|---|---|---|
| `DJANGO_EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | api | console backend in development, SMTP in production (since task 1.1) |
| `EMAIL_TIMEOUT` | api | `10` seconds for every SMTP connection (since task 9.0) |
| `MODERATION_EMAIL` | api | empty: reports are only logged. Set in production (since task 9.0) |
| `LEGACY_LIST_CREATION` | — | removed in task 9.6 with `/api/v1/` (it let backend tests and the e2e stack create legacy lists, since 1.4) |
| `RETIRE_LEGACY_LISTS` | migrate (once) | unset: `sharing.0011` stops while a list without an account is alive. `delete` deletes those lists instead (since 9.6; for development databases, or a V1 install moving on early) |
| `MEDIA_ROOT` | api, cleanup, worker | `/srv/media` (since task 2.3) |
| `DB_STATEMENT_TIMEOUT`, `DB_LOCK_TIMEOUT` | api / migrate (production) | api 20s and 5s; `migrate` runs with a statement timeout of 0 (since task 1.1) |
| `METADATA_FETCH_ENABLED` | api, worker | `true` (`false` disables fetching, for locked-down deployments; read from task 7.3) |
| `FETCH_BLOCKED_NETWORKS` | worker | empty: comma-separated CIDRs the fetcher never connects to, **added** to its built-in private and metadata ranges, which nothing can remove; checked at startup (since task 7.2) |
| `FETCH_TEST_HOSTS` | worker (e2e only) | empty. `fixture.test=fixture` in `e2e/compose.e2e.yaml` only ([13](13-SECURITY.md#ssrf-safe-fetcher)); a warning is logged when set (since task 7.3) |
| `WORKER_REPLICAS` | compose (production) | `2`: task processes, each running one task at a time (since task 7.1) |
| `MAINTENANCE_DIR` | nginx (production) | `./deploy/maintenance`: the maintenance page and its `on` switch; nginx answers 503 while the switch exists (since task 9.5) |
| `LOG_FORMAT` | api, worker, cleanup (production) | `json`: one JSON object per log line; `text` for the development format (since task 9.1) |
| `THROTTLE_*` (extended) | api | V1 defaults + new scopes ([13](13-SECURITY.md#rate-limits)); `THROTTLE_ACCOUNT` 300/hour since task 1.1; `THROTTLE_MEMBER_ADD` 60/hour per user since task 1.5; `THROTTLE_UPLOAD` 120/hour per user since task 2.3; `THROTTLE_RESTORE` 120/hour since task 3.3; `THROTTLE_GROUP_CREATE` 30/hour and `THROTTLE_GROUP_MANAGE` 600/hour since task 4.2; `THROTTLE_METADATA_REFRESH` 60/hour per user and `THROTTLE_DIRECTORY` 600/hour per IP since task 8.1; `THROTTLE_REPORT` 10/hour per user or IP since task 9.0 |

## Scheduled jobs

These run under supercronic from `backend/docker/crontab`.

| Schedule (UTC) | Command | Since |
|---|---|---|
| daily 03:00 | `cleanup_expired`: expired lists (sets `parent_deleted_at` on their branches first), throttle cache | V1, extended |
| daily 03:20 | `clearsessions` | V2 |
| every 5 minutes | `recover_stuck_tasks`: tasks left running by a worker that died run again, or fail after 3 runs | 7.1 |
| daily 03:30 | `prune_db_task_results --min-age-days 7`: records of tasks finished over 7 days ago | 7.1 |
| daily 03:40 | `purge_deleted_accounts`: erase accounts deleted more than 30 days ago (lists, memberships, personal data; [ADR-016](adr/ADR-016-account-deletion-grace-period.md)) | 3.0 |
| weekly Sun 04:00 | `cleanup_media`: delete files referenced by no row and no revision snapshot, older than 7 days | 2.3 (rows: list images, link icons including tombstones); revision snapshots and group images since 4.2 (snapshots were documented for 3.1 but missed until then); fetched icons in 7.3 |

## Backups

V1 had none documented. V2 holds account data and permanent lists, so backups become required:

- Daily `pg_dump -Fc` from the `db` container to a host path outside the volume, kept 14 days,
  with a restore tested monthly.
- `media` volume: daily `rsync`/`tar`. Files are content-addressed and immutable, so it's
  incremental by nature.
- Optional: WAL archiving for point-in-time recovery, if the host supports it.

Since task 9.4 these are host scripts, not services: `deploy/backup.sh` (the dump, checked
with `pg_restore --list`, and a tar of `media`; files mode 600; `BACKUP_KEEP_DAYS`, default 14)
and `deploy/restore.sh` (stops the app, recreates the database, replaces `media`, starts the
stack, which migrates). A restore into a separate compose project is the monthly test. Both
were run against the production stack: a small database came back in 13 s. The schedule and
commands are in [docs/deployment.md](../deployment.md#backups).

## Health checks and observability

- `/healthz` (V1, DB round-trip). The worker's compose healthcheck is `check_worker` (since
  7.1): it exits non-zero if a ready task has waited, or a task has been running, longer than
  10 minutes. The library has no heartbeat, so the queue itself is the signal; a worker that
  crashes exits and is restarted. `deploy/smoke-test.sh` checks that every replica is healthy
  and runs a task through it. A task that hangs ends its worker (the hard time limit above).
  **Compose never restarts an unhealthy container, and nothing alerts**: a worker that hangs
  outside a task stays hung until someone looks. Since task 9.4 the host script
  `deploy/autoheal.sh`, run from cron or a systemd timer, restarts unhealthy containers,
  reports stopped ones and passes its findings to `ALERT_COMMAND`
  ([docs/deployment.md](../deployment.md#monitoring)). It isn't a compose service, so no ADR;
  it was tested by making both workers unhealthy with a task stuck for an hour.
- **Structured logging** (since task 9.1): nginx gives each request an id (`$request_id`),
  writes it in its access log (`requests` format) and sends it as `X-Request-ID`;
  `config.middleware.request_id` adopts it (or makes one), echoes it back, and every api
  record carries it and the user id (`config/logging.py`). Production writes one JSON object
  per line (`LOG_FORMAT=text` keeps the development format). The api logs each task it queues
  with the task's id, which the worker's lines show, so a request can be followed into the
  worker. Container logs rotate at 5 × 20 MB (`compose.prod.yaml`). The inventory is in
  [21](21-SECURITY-REVIEW.md#logging).
- **Merge diagnostics:** every apply logs `{branch_id, fingerprint, decisions_count, outcome,
  error_code, duration_ms}`. Failures keep the request's fingerprint and the current one.
  `SyncRecord` keeps the successful ones.
- **Background task visibility:** `check_worker` prints the number of ready and running tasks
  and how long the oldest has waited on every check; `docker inspect` keeps the last few
  (since 7.1, instead of a separate `task_stats` command).
- **Error reporting:** errors go to the logs (with tracebacks and request ids), as in V1.
  Nothing reports them elsewhere: a deployment that wants Sentry or similar adds it later
  (`sentry-sdk` isn't a dependency, and nothing reads a `SENTRY_DSN`).
- No Prometheus or Grafana stack (prompt 15.3).

## Performance targets (initial)

| Operation | Target (p95, single host, 3 Gunicorn workers) | Measured (task 9.2) |
|---|---|---|
| List page API (detail + 100 links) | < 150 ms, ≤ 4 queries | 25 + 38 ms; 1 + 3 queries (+2 for a signed-in session) |
| Group workspace (group + 30 visible lists) | < 200 ms, ≤ 5 queries | 28 + 58 ms; 2 + 2 queries |
| `/r/{code}` redirect | < 50 ms, 1–2 queries | 22 ms; 1 query |
| Directory search (100k public lists) | < 300 ms | 236 ms for a word matching 17 % of all lists (334 ms before 9.2's index fix); 210 ms for a partial word; 46 ms for tags only; 79 ms newest first |
| Sync preview (100 links), postponed (ADR-015) | < 200 ms (3 snapshot reads + an in-memory plan) | |
| Sync apply (100 links), postponed (ADR-015) | < 500 ms | |
| Metadata fetch | asynchronous. 90 % of fetches finish within 15 s of creation | |

**Measured (task 9.2, 2026-10-30)** with `bash deploy/perf.sh`: the production stack (nginx,
3 Gunicorn workers, PostgreSQL 17) on one 4-core host with 7 GB, with the client on the same
host; 60 single requests per endpoint after a warm-up. The data: a 100-link public list, a
public group of 30 lists, 100,000 public lists (titles and descriptions from 16 words, two tags
each) and 20,000 rate-limit entries. Popular tags, which has no target, took 156 ms (it counts
the tags of every public list on each request). Rerun the script after changes that touch
these endpoints and on the production host before launch.

What the measurement found: a directory search with words scanned every row, because the
trigram index on `title` didn't match the `UPPER(title)` that Django's `icontains` compares.
The index is now on `UPPER(title)` ([05](05-DATABASE-DESIGN.md)), and the plan combines it with
the full-text index (database time 171 → 106 ms). What remains is ranking every match, which
grows with how common the word is.

Query budgets (`tests/test_query_counts.py`): every read endpoint is measured with little data
and at the sizes above, and must cost the same with both, within its budget. A throttled
request adds 8 statements of the PostgreSQL rate limiter, including Django's database cache
counting its rows on every write. That count grows with the cache table: at 20,000 entries it
stayed within the directory times above. Snapshots: 5.4 KiB stored for a typical 100-link list,
at most 322 KiB at the cap with every field full and incompressible (risk 27).

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
