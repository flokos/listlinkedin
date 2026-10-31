"""Moderation: delete a reported group (docs/v2/13-SECURITY.md#moderation)."""

from django.core.management.base import BaseCommand, CommandError

from apps.common import errors
from apps.groups import services
from apps.groups.models import Group


class Command(BaseCommand):
    help = (
        "Delete a group with its memberships; the lists in it are untouched. Without --yes, "
        "only shows what would be deleted."
    )

    def add_arguments(self, parser):
        parser.add_argument("code", help="The group's code, as in its address /g/{code}.")
        parser.add_argument("--reason", required=True, help="Why, for the log.")
        parser.add_argument("--yes", action="store_true", help="Really delete it.")

    def handle(self, *args, code: str, reason: str, yes: bool, **options):
        group = Group.objects.filter(code=code).first()
        if group is None:
            raise CommandError(f"There is no group with the code {code}.")
        summary = f"Group {code} (“{group.title}”, {group.visibility})"
        if not yes:
            raise CommandError(f"{summary} would be deleted. Add --yes to delete it.")
        try:
            services.delete_group_by_operator(code, reason=reason)
        except errors.DomainError as exc:
            raise CommandError(exc.message) from exc
        self.stdout.write(f"{summary} is deleted. Its lists are untouched.")
