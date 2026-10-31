from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.sharing.models import OWNER_ACTIVE, SharedLink, SharedList
from apps.sharing.services import metadata


class Command(BaseCommand):
    help = (
        "Queue a metadata fetch for live links whose stored metadata doesn't describe their "
        "current URL: links from before task 7.3, from while fetching was off, or whose fetch "
        "was lost. Run once after deploying 7.3; safe to run again."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit", type=int, default=1000, help="At most this many (default 1000)."
        )
        parser.add_argument("--dry-run", action="store_true", help="Only count them.")

    def handle(self, *args, limit, dry_run, **options):
        if not settings.METADATA_FETCH_ENABLED:
            self.stdout.write("Fetching is turned off (METADATA_FETCH_ENABLED): nothing queued.")
            return
        links = (
            SharedLink.objects.filter(deleted_at=None, shared_list__in=_active_lists())
            .only("pk", "destination_url", "metadata")
            .order_by("created_at", "pk")
        )
        stale = []
        for link in links.iterator(chunk_size=500):
            if not metadata.describes(link.metadata, link.destination_url):
                stale.append(link)
                if len(stale) >= limit:
                    break
        if not dry_run:
            # One transaction: the tasks are queued together, on commit. The worker spaces
            # requests to one host itself.
            with transaction.atomic():
                for link in stale:
                    metadata.request_fetch(link.pk, link.destination_url)
        verb = "Would queue" if dry_run else "Queued"
        self.stdout.write(f"{verb} {len(stale)} metadata fetch(es).")


def _active_lists():
    return SharedList.objects.filter(OWNER_ACTIVE).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
    )
