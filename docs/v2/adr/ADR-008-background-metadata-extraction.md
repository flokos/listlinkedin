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
- **Failures:** retried at most twice with backoff for timeouts and 5xx responses. After that,
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

Task 7.1 keeps this list accurate (it names the real files and settings once they exist). In
the switching PR, remove each item, in this order where it matters:

1. **Drain first.** Stop new enqueues (deploy the Celery enqueue point), let `db_worker` finish
   the ready tasks, then stop the old `worker`. Anything left is refilled by `backfill_metadata`.
2. **Drop the queue tables while the package is still installed:**
   `python manage.py migrate django_tasks_db zero` in a migration step of the release (record
   it in [06](../06-MIGRATION-PLAN.md) as one-way: the job history is discarded on purpose).
   Removing the app from `INSTALLED_APPS` first would leave its tables orphaned, because Django
   can then no longer unapply its migrations.
3. **Settings:** `django_tasks` and `django_tasks_db` in `INSTALLED_APPS`, the `TASKS` setting
   (and the test settings' `ImmediateBackend`, replaced by Celery's eager mode or direct calls).
4. **Dependencies:** both packages from `pyproject.toml` and `uv.lock`.
5. **Operations:** the `worker` service's `db_worker` command in both compose files, its
   healthcheck management command (oldest ready task, heartbeat), and the
   `prune_db_task_results` line in the `cleanup` crontab.
6. **Docs:** [14](../14-INFRASTRUCTURE.md#background-worker) (worker, health, the Redis and
   Celery rows under "not needed"), the deployment docs, D11 and D27 in
   [20](../20-DECISIONS-AND-OPEN-QUESTIONS.md), and CLAUDE.md's "Don't add Redis, Celery…" line,
   which must name the accepted ADR.
7. **If 7.1 took the fallback** (our own `metadata_fetch_job` table instead of
   django-tasks-db): its loop command, and a migration dropping the table, replace items 2–5.

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
