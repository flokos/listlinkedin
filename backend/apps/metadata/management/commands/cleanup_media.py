import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.groups.selectors import media_in_use as group_media
from apps.sharing.selectors import media_in_use as list_media
from apps.versioning.selectors import icons_in_snapshots

GRACE_DAYS = 7


class Command(BaseCommand):
    help = (
        "Delete media files that no list, link, group or revision refers to and that are older "
        f"than {GRACE_DAYS} days (docs/v2/14-INFRASTRUCTURE.md#scheduled-jobs)."
    )

    def handle(self, *args, **options):
        # The grace period covers uploads whose row isn't committed yet, and files that a
        # restore or a later write could still point to again. A re-uploaded identical image
        # refreshes its file's mtime (apps.metadata.images.store), so it isn't deleted.
        root = Path(settings.MEDIA_ROOT)
        cutoff = time.time() - GRACE_DAYS * 24 * 60 * 60
        # Read the references *after* listing the files: a file stored after the listing
        # isn't considered, and a reference committed before the query is seen.
        candidates = [p for p in root.rglob("*") if p.suffix in (".webp", ".tmp") and p.is_file()]
        in_use = list_media() | group_media() | icons_in_snapshots()
        deleted = 0
        for path in candidates:
            if path.relative_to(root).as_posix() in in_use or path.stat().st_mtime > cutoff:
                continue
            path.unlink(missing_ok=True)
            deleted += 1
        self.stdout.write(
            f"Deleted {deleted} unused media files; kept {len(candidates) - deleted}."
        )
