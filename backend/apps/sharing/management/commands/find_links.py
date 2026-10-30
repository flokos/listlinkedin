"""Moderation: find the lists that link to a host (docs/v2/13-SECURITY.md#moderation)."""

from django.core.management.base import BaseCommand

from apps.sharing.services import moderation


class Command(BaseCommand):
    help = (
        "List every live link to a host or its subdomains, with its list, for example to "
        "sweep a phishing domain before blocking it with BLOCKED_DESTINATION_HOSTS."
    )

    def add_arguments(self, parser):
        parser.add_argument("host", help="A host name, e.g. example.com.")

    def handle(self, *args, host: str, **options):
        found = moderation.find_links(host)
        for row in found:
            owner = f"user {row['owner']}" if row["owner"] else "edit link"
            self.stdout.write(
                f"{row['list']}  {row['visibility']:<8}  {owner}  “{row['title']}”  {row['url']}"
            )
        self.stdout.write(f"{len(found)} link{'' if len(found) == 1 else 's'} to {host}.")
