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
`prune_db_task_results` cleanup step removed. Estimated at a day or two including tests.
