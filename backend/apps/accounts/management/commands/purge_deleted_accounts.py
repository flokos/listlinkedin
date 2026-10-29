from django.core.management.base import BaseCommand

from apps.accounts.models import DELETION_GRACE
from apps.accounts.services import purge_deleted_accounts


class Command(BaseCommand):
    help = (
        f"Erase accounts deleted more than {DELETION_GRACE.days} days ago: their lists, "
        "memberships and personal data (docs/v2/adr/ADR-016)."
    )

    def handle(self, *args, **options):
        erased = purge_deleted_accounts()
        self.stdout.write(f"Erased {erased} deleted account(s).")
