"""Moderation: delete a reported list (docs/v2/13-SECURITY.md#moderation)."""

from django.core.management.base import BaseCommand, CommandError

from apps.common import errors
from apps.sharing.models import SharedList
from apps.sharing.services import moderation


class Command(BaseCommand):
    help = (
        "Delete a list with its links, short URLs and memberships. Without --yes, only shows "
        "what would be deleted."
    )

    def add_arguments(self, parser):
        parser.add_argument("code", help="The list's code, as in its address /l/{code}.")
        parser.add_argument("--reason", required=True, help="Why, for the log.")
        parser.add_argument("--yes", action="store_true", help="Really delete it.")

    def handle(self, *args, code: str, reason: str, yes: bool, **options):
        shared_list = SharedList.objects.filter(public_code=code).first()
        if shared_list is None:
            raise CommandError(f"There is no list with the code {code}.")
        live = shared_list.links.filter(deleted_at__isnull=True).count()
        summary = f"List {code} (“{shared_list.title}”, {shared_list.visibility}, {live} links)"
        if not yes:
            raise CommandError(f"{summary} would be deleted. Add --yes to delete it.")
        try:
            moderation.delete_list(code, reason=reason)
        except errors.DomainError as exc:
            raise CommandError(exc.message) from exc
        self.stdout.write(f"{summary} is deleted.")
