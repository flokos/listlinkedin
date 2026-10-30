"""Background tasks (docs/v2/adr/ADR-008-background-metadata-extraction.md).

The one place that queues work. Code elsewhere calls the functions here, never the task
library, so the runner can be replaced later without touching callers (ADR-008, "Moving to
Celery later"). The `worker` service runs queued tasks (`manage.py db_worker`).

Rules for every task:

- **Thin:** a task calls plain functions that hold the actual work, so the same code runs
  under any runner and is tested without one.
- **Idempotent, with its state in the database:** a task may run twice (`recover_stuck_tasks`
  re-queues one whose worker died) or late (after a retry pause), so it re-reads what it works
  on and does nothing if that changed. Arguments are ids and values, never model instances.
- **Short:** well within `settings.TASK_STALE_AFTER`; longer ones count as stuck.
- **Temporary failures** (a timeout, a 5xx answer) raise `TemporaryFailure`; the task then
  calls `retry_or_give_up`. Any other exception fails the task for good, as a bug.

Task 7.3 adds `fetch_link_metadata` and `enqueue_metadata_fetch(link_id, url)` here.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

MAX_ATTEMPTS = 3
# The pause before attempts 2 and 3.
RETRY_DELAYS = (timedelta(seconds=30), timedelta(minutes=5))


class TemporaryFailure(Exception):
    """A failure worth trying again later, such as a timeout or a 5xx answer."""


def enqueue_on_commit(task, *args, **kwargs) -> None:
    """Queue `task` once the current transaction commits (at once, outside a transaction).

    A rolled-back change queues nothing, and a worker never sees a task about a row that isn't
    committed yet. The task library inserts its row immediately, so this is the only safe way
    to queue from a request.
    """
    transaction.on_commit(lambda: task.enqueue(*args, **kwargs))


def retry_or_give_up(task, attempt: int, *args, **kwargs) -> bool:
    """After a `TemporaryFailure` in `attempt` (1-based): queue the next attempt after a pause
    and return True, or return False if that was the last one. The next attempt is called
    with the same arguments and `attempt=attempt + 1`."""
    if attempt >= MAX_ATTEMPTS:
        return False
    later = task.using(run_after=timezone.now() + RETRY_DELAYS[attempt - 1])
    enqueue_on_commit(later, *args, attempt=attempt + 1, **kwargs)
    return True
