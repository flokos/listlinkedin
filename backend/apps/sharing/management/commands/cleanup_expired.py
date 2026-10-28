from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone

from apps.sharing.models import SharedList

LOCK_KEY = "cleanup_expired"


class Command(BaseCommand):
    help = (
        "Physically delete expired lists together with their links and short redirects, "
        "and prune expired rate-limit entries."
    )

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=500)

    def handle(self, *args, batch_size: int, **options):
        # Overlapping runs (e.g. a manual run during the scheduled one) would delete the same
        # rows in different orders and could deadlock. A session advisory lock allows one.
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(hashtextextended(%s, 0))", [LOCK_KEY])
            if not cursor.fetchone()[0]:
                self.stdout.write("Another cleanup run is in progress; skipping.")
                return
        try:
            self._cleanup(batch_size)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(hashtextextended(%s, 0))", [LOCK_KEY])

    def _cleanup(self, batch_size: int) -> None:
        now = timezone.now()
        totals: dict[str, int] = {}

        # Small batches in short transactions keep locks brief, so the API is never blocked
        # for long. Re-running is harmless: already-deleted lists simply are not found.
        while True:
            with transaction.atomic():
                batch = list(
                    SharedList.objects.filter(expires_at__lte=now).values_list("pk", flat=True)[
                        :batch_size
                    ]
                )
                if not batch:
                    break
                _, per_model = SharedList.objects.filter(pk__in=batch).delete()
            for label, count in per_model.items():
                totals[label] = totals.get(label, 0) + count

        self.stdout.write(
            "Deleted {lists} expired list(s), {links} link(s), {redirects} redirect(s).".format(
                lists=totals.get("sharing.SharedList", 0),
                links=totals.get("sharing.SharedLink", 0),
                redirects=totals.get("shortener.ShortRedirect", 0),
            )
        )
        self.stdout.write(f"Pruned {_prune_rate_limit_cache(now)} expired rate-limit entries.")


def _prune_rate_limit_cache(now) -> int:
    """Delete expired throttle rows.

    Django's DatabaseCache only removes expired rows once the table exceeds MAX_ENTRIES,
    and it counts every row on every write, so pruning daily keeps both small.
    """
    cache_config = settings.CACHES["default"]
    if cache_config["BACKEND"] != "django.core.cache.backends.db.DatabaseCache":
        return 0
    table = connection.ops.quote_name(cache_config["LOCATION"])
    with connection.cursor() as cursor:
        cursor.execute(f"DELETE FROM {table} WHERE expires < %s", [now])
        return cursor.rowcount
