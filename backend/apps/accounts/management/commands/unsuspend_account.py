"""Moderation: lift an account's suspension (docs/v2/13-SECURITY.md#moderation)."""

from django.core.management.base import BaseCommand, CommandError

from apps.accounts import services
from apps.common import errors


class Command(BaseCommand):
    help = (
        "Let a suspended account sign in again. Lists and groups unpublished with it stay "
        "private until their owner changes them."
    )

    def add_arguments(self, parser):
        parser.add_argument("account", help="The account's email address or user id.")
        parser.add_argument("--reason", required=True, help="Why, for the log.")

    def handle(self, *args, account: str, reason: str, **options):
        try:
            user = services.find_account(account)
            services.unsuspend_account(user, reason=reason)
        except errors.DomainError as exc:
            raise CommandError(exc.message) from exc
        self.stdout.write(f"Account {user.pk} can sign in again.")
