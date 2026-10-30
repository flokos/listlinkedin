from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django_tasks_db.compat import TaskResultStatus
from django_tasks_db.models import DBTaskResult

from apps.metadata.tasks import MAX_ATTEMPTS

WORKER_LOST = "apps.metadata.tasks.WorkerLost"


class Command(BaseCommand):
    help = (
        "Take back tasks left running by a worker that died (killed, restarted, out of "
        "memory): run them again, or fail them after MAX_ATTEMPTS runs. Every 5 minutes "
        "(docker/crontab)."
    )

    def handle(self, *args, **options):
        # The task library never does this itself: a task whose worker died stays RUNNING
        # forever. Tasks are idempotent (apps.metadata.tasks), so running one again is safe.
        stale = timezone.now() - settings.TASK_STALE_AFTER
        requeued = failed = 0
        with transaction.atomic():
            stuck = (
                DBTaskResult.objects.running()
                .filter(started_at__lt=stale)
                .select_for_update(skip_locked=True)
            )
            for result in stuck:
                if len(result.worker_ids) < MAX_ATTEMPTS:  # one worker id per run
                    result.status = TaskResultStatus.READY
                    result.started_at = None
                    result.save(update_fields=["status", "started_at"])
                    requeued += 1
                else:
                    result.status = TaskResultStatus.FAILED
                    result.finished_at = timezone.now()
                    result.exception_class_path = WORKER_LOST
                    result.traceback = "The worker stopped while running this task."
                    result.save(
                        update_fields=["status", "finished_at", "exception_class_path", "traceback"]
                    )
                    failed += 1
        self.stdout.write(f"Re-queued {requeued} stuck task(s); failed {failed}.")
