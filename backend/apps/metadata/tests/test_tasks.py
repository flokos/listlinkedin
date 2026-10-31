"""The task queue (docs/v2/adr/ADR-008): queuing on commit, the real worker, retries, the
health check and recovery of tasks a dead worker left running."""

from datetime import timedelta

import pytest
from django.core.management import CommandError, call_command
from django.db import transaction
from django.utils import timezone
from django_tasks_db.compat import TaskResultStatus
from django_tasks_db.models import DBTaskResult

from apps.metadata.tasks import RETRY_DELAYS, enqueue_on_commit

from .sample_tasks import echo, flaky

pytestmark = pytest.mark.django_db
# Tests that run the worker commit for real: it closes database connections between tasks,
# which a test wrapped in one transaction can't survive. on_commit then behaves as in production.
with_commits = pytest.mark.django_db(transaction=True)


def run_worker():
    """Run every ready task with the production worker command, then return."""
    call_command("db_worker", "--batch", "--no-startup-delay", "--no-reload", verbosity=0)


def results():
    return list(DBTaskResult.objects.order_by("enqueued_at"))


@with_commits
def test_tasks_are_queued_only_when_the_transaction_commits():
    with transaction.atomic():
        enqueue_on_commit(echo, "kept")
        assert not DBTaskResult.objects.exists()  # not before the commit
    try:
        with transaction.atomic():
            enqueue_on_commit(echo, "rolled back")
            raise RuntimeError("roll back")
    except RuntimeError:
        pass
    assert [r.args_kwargs["args"] for r in results()] == [["kept"]]

    run_worker()
    (result,) = results()
    assert result.status == TaskResultStatus.SUCCESSFUL
    assert result.return_value == "kept"


@with_commits
def test_a_temporary_failure_is_retried_after_a_pause():
    enqueue_on_commit(flaky, 1)
    run_worker()
    first, retry = results()
    assert first.return_value == "retrying after attempt 1"
    assert retry.status == TaskResultStatus.READY
    assert retry.args_kwargs == {"args": [1], "kwargs": {"attempt": 2}}
    wait = retry.run_after - first.finished_at
    assert RETRY_DELAYS[0] - timedelta(seconds=5) < wait <= RETRY_DELAYS[0]

    run_worker()  # not due yet: nothing runs
    assert DBTaskResult.objects.get(pk=retry.pk).status == TaskResultStatus.READY
    DBTaskResult.objects.filter(pk=retry.pk).update(run_after=timezone.now())
    run_worker()
    assert DBTaskResult.objects.get(pk=retry.pk).return_value == "done on attempt 2"


@with_commits
def test_retries_stop_after_the_last_attempt():
    enqueue_on_commit(flaky, 99)
    for _ in range(3):
        run_worker()
        DBTaskResult.objects.filter(status=TaskResultStatus.READY).update(run_after=timezone.now())
    assert [r.return_value for r in results()] == [
        "retrying after attempt 1",
        "retrying after attempt 2",
        "gave up after attempt 3",
    ]


def make_result(status=TaskResultStatus.READY, *, age=timedelta(0), **fields):
    result = DBTaskResult.objects.create(
        task_path="apps.metadata.tests.sample_tasks.echo",
        args_kwargs={"args": ["x"], "kwargs": {}},
        backend_name="default",
        status=status,
        **fields,
    )
    # enqueued_at is auto_now_add: set the age afterwards.
    DBTaskResult.objects.filter(pk=result.pk).update(enqueued_at=timezone.now() - age)
    return result


def test_the_health_check_reports_a_queue_nobody_works():
    call_command("check_worker", verbosity=0)
    make_result(age=timedelta(minutes=2))
    # A retry waiting for its pause doesn't count, however long ago it was first queued.
    make_result(age=timedelta(hours=1), run_after=timezone.now() + timedelta(minutes=3))
    call_command("check_worker", verbosity=0)

    make_result(age=timedelta(minutes=11))
    with pytest.raises(CommandError, match="1 waiting"):
        call_command("check_worker", verbosity=0)


def test_the_health_check_reports_a_stuck_task():
    make_result(TaskResultStatus.RUNNING, started_at=timezone.now() - timedelta(minutes=1))
    call_command("check_worker", verbosity=0)
    make_result(TaskResultStatus.RUNNING, started_at=timezone.now() - timedelta(minutes=11))
    with pytest.raises(CommandError, match="1 running for over"):
        call_command("check_worker", verbosity=0)


@with_commits
def test_tasks_left_running_by_a_dead_worker_run_again_or_fail():
    long_ago = timezone.now() - timedelta(minutes=11)
    running = make_result(TaskResultStatus.RUNNING, started_at=timezone.now(), worker_ids=["w1"])
    once = make_result(TaskResultStatus.RUNNING, started_at=long_ago, worker_ids=["w1"])
    thrice = make_result(
        TaskResultStatus.RUNNING, started_at=long_ago, worker_ids=["w1", "w2", "w3"]
    )

    call_command("recover_stuck_tasks", verbosity=0)

    def status(result):
        return DBTaskResult.objects.get(pk=result.pk).status

    assert status(running) == TaskResultStatus.RUNNING  # still within its time
    assert status(once) == TaskResultStatus.READY
    assert status(thrice) == TaskResultStatus.FAILED
    assert DBTaskResult.objects.get(pk=thrice.pk).exception_class_path.endswith("WorkerLost")

    run_worker()  # the re-queued task runs to completion
    assert status(once) == TaskResultStatus.SUCCESSFUL
