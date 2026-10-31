"""Moderation: suspend an account (docs/v2/13-SECURITY.md#moderation)."""

from django.core.management.base import BaseCommand, CommandError

from apps.accounts import services
from apps.common import errors


class Command(BaseCommand):
    help = (
        "Stop an account from signing in and end its sessions on every device. With "
        "--unpublish, its public and unlisted lists and groups become private too."
    )

    def add_arguments(self, parser):
        parser.add_argument("account", help="The account's email address or user id.")
        parser.add_argument("--reason", required=True, help="Why, for the log.")
        parser.add_argument(
            "--unpublish", action="store_true", help="Also make its lists and groups private."
        )

    def handle(self, *args, account: str, reason: str, unpublish: bool, **options):
        try:
            user = services.find_account(account)
            lists, groups = services.suspend_account(user, reason=reason, unpublish=unpublish)
        except errors.DomainError as exc:
            raise CommandError(exc.message) from exc
        message = f"Account {user.pk} is suspended."
        if unpublish:
            message += f" {lists} lists and {groups} groups are private now."
        self.stdout.write(message)
