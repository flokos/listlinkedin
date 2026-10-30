"""Moderation: make a reported list private (docs/v2/13-SECURITY.md#moderation)."""

from django.core.management.base import BaseCommand, CommandError

from apps.common import errors
from apps.sharing.services import moderation


class Command(BaseCommand):
    help = (
        "Make a list private: only its owner and the people it's shared with can still open "
        "it, and its short URLs stop working for everyone else."
    )

    def add_arguments(self, parser):
        parser.add_argument("code", help="The list's code, as in its address /l/{code}.")
        parser.add_argument("--reason", required=True, help="Why, for the log.")

    def handle(self, *args, code: str, reason: str, **options):
        try:
            shared_list = moderation.unpublish_list(code, reason=reason)
        except errors.DomainError as exc:
            raise CommandError(exc.message) from exc
        self.stdout.write(f"List {code} (“{shared_list.title}”) is private now.")
