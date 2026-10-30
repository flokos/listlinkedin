"""Moderation: make a reported group private (docs/v2/13-SECURITY.md#moderation)."""

from django.core.management.base import BaseCommand, CommandError

from apps.common import errors
from apps.groups import services


class Command(BaseCommand):
    help = "Make a group private: only its owner and members can still open it."

    def add_arguments(self, parser):
        parser.add_argument("code", help="The group's code, as in its address /g/{code}.")
        parser.add_argument("--reason", required=True, help="Why, for the log.")

    def handle(self, *args, code: str, reason: str, **options):
        try:
            group = services.unpublish_group(code, reason=reason)
        except errors.DomainError as exc:
            raise CommandError(exc.message) from exc
        self.stdout.write(f"Group {code} (“{group.title}”) is private now.")
