"""Tasks used only by test_tasks.py. The worker imports a task by its module path, so they
live in a module of their own."""

from django_tasks import task

from apps.metadata.tasks import TemporaryFailure, retry_or_give_up


@task()
def echo(value: str) -> str:
    return value


@task()
def flaky(fail_times: int, attempt: int = 1) -> str:
    """Fails temporarily on its first `fail_times` attempts, retrying as tasks should."""
    try:
        if attempt <= fail_times:
            raise TemporaryFailure(f"attempt {attempt}")
        return f"done on attempt {attempt}"
    except TemporaryFailure:
        if retry_or_give_up(flaky, attempt, fail_times):
            return f"retrying after attempt {attempt}"
        return f"gave up after attempt {attempt}"
