# ADR-008: Background metadata extraction on a PostgreSQL-backed worker

- Status: Accepted (2026-10-28, V2 planning)
- Related: [13 SSRF-safe fetcher](../13-SECURITY.md#ssrf-safe-fetcher), [14 Background worker](../14-INFRASTRUCTURE.md#background-worker)

## Context

V2 fetches page titles, descriptions, favicons and Open Graph images for links. V1
deliberately never fetched URLs, because of SSRF risk and wrong results for intranet links.
Fetching is slow and failure-prone, and the production API runs 3 synchronous Gunicorn
workers. The prompt asks whether Celery is justified, says not to add RabbitMQ just because
Celery supports it, and requires that delayed results never overwrite manual edits.

## Decision

- **Asynchronous** extraction in a separate `worker` container (same image) using
  **django-tasks** (backport of Django 6.0's Tasks API [R2][R4]) with the **django-tasks-db**
  PostgreSQL backend (`db_worker`, `SKIP LOCKED`) [R5]. Tasks are enqueued with
  `transaction.on_commit`. Both packages are pinned exactly.
- **Field provenance:** fetched values go only to `SharedLink.metadata` (JSON) and
  `metadata_fetched_at`. User fields (`title`, `description`, `icon`) are never written by the
  worker. Display precedence is user → fetched → fallback. Fetched metadata is not versioned
  and not synchronized.
- **Stale-result guard:** the worker stores results with
  `UPDATE … WHERE id = ? AND destination_url = <fetched url> AND deleted_at IS NULL`, so a URL
  edit or a deletion during the fetch discards the result.
- **Security:** only `metadata/fetcher.py` fetches user URLs (resolve, validate every address,
  pin the connection, manual redirects, ports 80/443, size, time and type limits). Images go
  through the Pillow pipeline ([ADR-012](ADR-012-media-and-images.md)). No headless browser.
- **Failures:** retried at most twice with backoff for timeouts and 5xx responses (since 7.1:
  the library has no retries, so `metadata/tasks.retry_or_give_up` queues the next attempt
  with a `run_after` 30 s, then 5 min, later). After that,
  `metadata.status = "unavailable"` with an error code, and manual entry always works.
  Refreshing is manual (≤1/hour per link) or happens on URL change.

## Alternatives considered

- **Synchronous fetch in the request:** up to 10 s per request on a sync worker, which is
  easy to exhaust and an SSRF surface inside the API process.
- **Celery + Redis or RabbitMQ:** a broker, worker and beat for one low-volume job type.
  PostgreSQL already provides a reliable queue with `SKIP LOCKED`.
- **Client-side fetching:** CORS blocks most sites. It would leak users' IPs to every site and
  can't produce trusted, re-encoded images.
- **A custom job table:** kept as the documented fallback (~100 lines) if django-tasks-db
  (beta) proves unsuitable.

## Verified in task 7.1

Read in the pinned wheels' source (2026-10-30) and confirmed on the running stack:

- `db_worker` runs one task at a time per process, claims with `SELECT … FOR UPDATE SKIP
  LOCKED`, and on the first SIGTERM finishes its current task before exiting. Production runs
  two replicas (`WORKER_REPLICAS`).
- **No retries, no heartbeat, and no recovery of a task whose worker died** (it stays
  `RUNNING` for ever). Hence: retries through `run_after` (above); a health check on the
  queue itself (`check_worker`: a ready task waiting, or one running, longer than
  `TASK_STALE_AFTER`, 10 minutes); and `recover_stuck_tasks` every 5 minutes, which runs such
  a task again, or fails it after 3 runs. Tasks must therefore be idempotent.
- `enqueue()` inserts the row at once (no `on_commit` of its own), so the enqueue point wraps
  it in `transaction.on_commit`.
- The immediate backend can't defer a task, so tests use the database backend and run queued
  tasks with `db_worker --batch` in tests that really commit.
- The Django app label of django-tasks-db is **`django_tasks_database`** (its tables and
  migrations), not the module name.

The library is adopted; the fallback (a job table of our own) isn't needed.

Added in task 7.2: a **hard time limit**. Every task is declared with
`apps.metadata.tasks.background_task`, which runs it under a timer thread: past
`HARD_TIME_LIMIT` (120 s) the worker process exits with status 70. That covers a hang the
fetcher's own timeouts can't, such as a DNS lookup stuck in C code; compose restarts the
worker (`restart: unless-stopped`) and `recover_stuck_tasks` runs the task again. Compose
itself never restarts an *unhealthy* container, so a hang outside any task is still only
reported; phase 9 adds a recommendation (task 9.4).

## Consequences

- One new long-running service, plus queue pruning in `cleanup`.
- A manual title always wins. Users can clear it to fall back to the fetched one.
- Moving to Django 6.2 later makes the API built in. Only the DB backend package remains.

## Moving to Celery later

Added 2026-10-30 at the user's request; the decision above is unchanged. Celery (with Redis
or RabbitMQ) stays out of V2, but may replace the database-backed queue after V2, for example
if job types, volume or hosts grow, or Redis arrives for another reason. Task 7.1 keeps that
switch small by holding these boundaries:

- **One enqueue point.** Code outside the worker calls `metadata/tasks.py`
  (`enqueue_metadata_fetch(link_id)`, inside `transaction.on_commit`), never the task library.
- **Thin task wrappers.** The work lives in plain functions (`fetcher.py`, `parser.py`, the
  conditional store); the task only calls them, so the same code runs under any runner.
- **State in the database, not in the queue.** Results go to `SharedLink.metadata`; a job
  carries only the link id and the URL it expects, and the stale-result guard makes a repeated,
  late or lost job harmless. Switching never migrates data: lost fetches are refilled by
  `backfill_metadata`.

A later switch then means: a superseding ADR; the broker service in compose with its
deployment, backup and monitoring notes; the wrapper and enqueue point rewritten for Celery
and the worker command replaced; the old queue drained or `backfill_metadata` run; and the
old pieces below removed. Estimated at a day or two including tests.

### What the database queue adds, to remove when switching

As built in task 7.1. In the switching PR, remove each item, in this order where it matters:

1. **Drain first.** Stop new enqueues (deploy the Celery version of
   `apps/metadata/tasks.py`), let `db_worker` finish the ready tasks, then stop the old
   `worker`. Anything left is refilled by `backfill_metadata` (7.3).
2. **Drop the queue tables while the package is still installed:**
   `python manage.py migrate django_tasks_database zero` (the app label, not the module name)
   in a migration step of the release, recorded in [06](../06-MIGRATION-PLAN.md) as one-way:
   the task history is discarded on purpose. Removing the app from `INSTALLED_APPS` first would
   leave its tables orphaned, because Django can then no longer unapply its migrations.
3. **Settings** (`config/settings/base.py`): `django_tasks` and `django_tasks_db` in
   `INSTALLED_APPS`, and `TASKS`. `TASK_STALE_AFTER` and `METADATA_FETCH_ENABLED` stay if
   their uses do.
4. **Code:** `enqueue_on_commit`, `retry_or_give_up` and `background_task` (django-tasks'
   `task` plus the hard time limit) in `apps/metadata/tasks.py`, rewritten for Celery (its own
   retries and time limits can replace them); the `@background_task` declarations there and
   in `apps/metadata/tests/sample_tasks.py`; the management commands `check_worker` and
   `recover_stuck_tasks` (`apps/metadata/management/commands/`), which read the queue table,
   rewritten for Celery or removed; and `run_worker()` in `apps/metadata/tests/test_tasks.py`.
5. **Dependencies:** `django-tasks` and `django-tasks-db[compat]` from `pyproject.toml`, then
   `uv lock`.
6. **Operations:** the `worker` service in `compose.yaml` and `compose.prod.yaml` (its
   `db_worker` command and its `check_worker` healthcheck; `WORKER_REPLICAS` may stay as the
   Celery worker count), the `recover_stuck_tasks` and `prune_db_task_results` lines in
   `backend/docker/crontab`, and the two worker checks in `deploy/smoke-test.sh`, which queue a
   sample task and read the queue table.
7. **Docs:** [14](../14-INFRASTRUCTURE.md#background-worker) (worker, scheduled jobs, health,
   the Redis and Celery rows under "not needed"), the deployment section of the README, D11
   and D27 in [20](../20-DECISIONS-AND-OPEN-QUESTIONS.md), CLAUDE.md's `metadata` row and its
   "Don't add Redis, Celery…" line, which must name the accepted ADR, and this section.

### Background work from earlier phases

No phase before 7 uses a task queue: V1 and phases 1–5 run everything either in the request
or as scheduled management commands. A move to Celery (or Redis arriving with it) doesn't have
to change any of them, but each is a candidate, and none should move silently:

| Work | Today | If Celery (or Redis) arrives |
|---|---|---|
| Scheduled jobs: `cleanup_expired` (daily 03:00), `clearsessions` (03:20), `purge_deleted_accounts` (03:40), `cleanup_media` (Sundays 04:00), and `prune_db_task_results` from 7.1 | supercronic in the `cleanup` container, `backend/docker/crontab` | **Default: stay on cron.** Moving them to Celery beat is optional: each task calls the same command logic, and beat must run as exactly one instance. Only `cleanup_expired` holds a single-instance advisory lock today; the others rely on one `cleanup` container. The `cleanup` container goes only if every line moves |
| Email: verification, password reset (allauth) | sent synchronously in the request through `EMAIL_BACKEND` (SMTP in production) | A candidate for a background task (through an enqueue point, as above), so a slow relay doesn't hold a Gunicorn worker. **Gap (2026-10-30):** no `EMAIL_TIMEOUT` is set, so a hanging relay holds the request until Gunicorn's 30 s timeout; setting one is a small, separate fix |
| Image uploads (list and group images, link icons) | re-encoded synchronously in the request, outside the row lock ([ADR-012](ADR-012-media-and-images.md)); ≤2 MB | Stays synchronous: the user waits for the result and the work is bounded |
| Rate-limit counters, sessions | PostgreSQL `DatabaseCache` with advisory locks (exact under concurrency, V1); database sessions | Not Celery. If Redis arrives, moving either is a separate decision with its own ADR, and must keep the throttles exact under concurrency |

Unchanged by a switch: the fetcher, parser and store step; `SharedLink.metadata` and the
stale-result guard; the `refresh-metadata` endpoint and its throttle; `backfill_metadata`;
`METADATA_FETCH_ENABLED`; the worker's egress restrictions.
