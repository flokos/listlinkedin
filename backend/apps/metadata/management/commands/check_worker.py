from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import F, Min, Value
from django.db.models.functions import Coalesce, NullIf
from django.utils import timezone
from django_tasks_db.models import DBTaskResult, get_date_max


class Command(BaseCommand):
    help = (
        "The worker's health check: fail if a ready task has waited, or a task has been "
        "running, longer than TASK_STALE_AFTER (docs/v2/14-INFRASTRUCTURE.md)."
    )

    def handle(self, *args, **options):
        # The library has no worker heartbeat; the queue itself shows whether it is worked.
        # A worker that crashes exits, and compose restarts it.
        now = timezone.now()
        stale = now - settings.TASK_STALE_AFTER
        ready = DBTaskResult.objects.ready()
        # A deferred task (a retry) waits from its run_after, not from when it was queued.
        waiting_since = Coalesce(NullIf(F("run_after"), Value(get_date_max())), F("enqueued_at"))
        oldest = ready.annotate(since=waiting_since).aggregate(oldest=Min("since"))["oldest"]
        waiting = ready.annotate(since=waiting_since).filter(since__lt=stale).count()
        running = DBTaskResult.objects.running()
        stuck = running.filter(started_at__lt=stale).count()
        # Printed on every check: `docker inspect` keeps the last few, a queue overview.
        summary = (
            f"{ready.count()} ready (oldest waiting {_age(now, oldest)}), {running.count()} running"
        )
        if waiting or stuck:
            raise CommandError(
                f"{summary}: {waiting} waiting and {stuck} running for over "
                f"{settings.TASK_STALE_AFTER}."
            )
        self.stdout.write(f"Task queue OK: {summary}.")


def _age(now, since) -> str:
    return "-" if since is None else f"{int((now - since).total_seconds())}s"
