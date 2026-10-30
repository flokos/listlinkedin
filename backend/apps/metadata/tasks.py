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
- **Short:** well within `HARD_TIME_LIMIT`. Every task is declared with `@background_task`,
  which ends the worker process if a task runs past it (a hang, even inside C code such as a
  DNS lookup): compose restarts the worker and `recover_stuck_tasks` runs the task again.
- **Temporary failures** (a timeout, a 5xx answer) raise `TemporaryFailure`; the task then
  calls `retry_or_give_up`. Any other exception fails the task for good, as a bug.

Task 7.3 adds `fetch_link_metadata` and `enqueue_metadata_fetch(link_id, url)` here.
"""

import functools
import logging
import os
import threading
from contextlib import contextmanager
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django_tasks import task

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
# Far beyond a real task (a fetch takes at most a few times 10 s), far below TASK_STALE_AFTER.
HARD_TIME_LIMIT = 120  # seconds
EXIT_HUNG = 70  # the worker's exit status when a task hung (EX_SOFTWARE)
# The pause before attempts 2 and 3.
RETRY_DELAYS = (timedelta(seconds=30), timedelta(minutes=5))


class TemporaryFailure(Exception):
    """A failure worth trying again later, such as a timeout or a 5xx answer."""


def background_task(function=None, **options):
    """Declare a task: `django_tasks.task(**options)` with the hard time limit around it."""

    def decorate(work):
        @functools.wraps(work)  # keeps the module path the worker imports the task by
        def limited(*args, **kwargs):
            with hard_time_limit(HARD_TIME_LIMIT, work.__qualname__):
                return work(*args, **kwargs)

        return task(**options)(limited)

    return decorate if function is None else decorate(function)


@contextmanager
def hard_time_limit(seconds: float, what: str):
    """End this process if the block runs longer than `seconds`. A timer thread does it, so
    it works even when the block is stuck in C code that never returns to Python."""
    timer = threading.Timer(seconds, _abandon, args=(what, seconds))
    timer.daemon = True
    timer.start()
    try:
        yield
    finally:
        timer.cancel()


def _abandon(what: str, seconds: float) -> None:
    logger.critical(
        "Task %s ran over %s s; ending the worker process so it restarts. "
        "recover_stuck_tasks will run the task again.",
        what,
        seconds,
    )
    exit_process(EXIT_HUNG)


exit_process = os._exit  # replaced in tests


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
