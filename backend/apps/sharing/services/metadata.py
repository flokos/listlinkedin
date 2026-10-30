"""Fetched metadata on links (docs/v2/adr/ADR-008-background-metadata-extraction.md).

`SharedLink.metadata` holds what the metadata worker found for one URL:

    {"link_url": <the link URL it describes>, "status": "ready" | "unavailable",
     "title", "description", "site_name", "icon", "image", "final_url", "error"}

Values count only while `link_url` is the link's current URL (selectors.current_metadata), so
a URL edit never shows another page's title. They are never content: storing them changes no
user field, writes no revision and leaves `updated_at` alone (invariant 6).

The `metadata` app fetches; this module, in the app that owns links, decides when to ask for a
fetch and stores the result.
"""

from uuid import UUID

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import Throttled

from apps.common import errors
from apps.metadata import tasks

from ..models import SharedLink
from ..policy import Action, can
from ..selectors import Principal
from .lists import _lock, denied

REFRESH_INTERVAL = 60 * 60  # seconds: at most one manual refresh per link per hour
READY, UNAVAILABLE = "ready", "unavailable"


def describes(metadata: dict | None, url: str) -> bool:
    """`metadata` is a finished fetch (ready or unavailable) of exactly `url`."""
    return bool(metadata) and metadata.get("link_url") == url and "status" in metadata


def request_fetch(link_id: UUID, url: str) -> None:
    """Fetch the page behind a link once the current transaction commits, unless fetching
    is off. Called on create, on a URL change, and for restored or copied links whose stored
    metadata is for another URL."""
    if settings.METADATA_FETCH_ENABLED:
        tasks.enqueue_metadata_fetch(link_id, url)


def request_if_stale(link: SharedLink) -> None:
    if not describes(link.metadata, link.destination_url):
        request_fetch(link.pk, link.destination_url)


def still_wanted(link_id: str, url: str) -> bool:
    """The task's guard: the link is live and still has the URL the task was queued for."""
    return SharedLink.objects.filter(pk=link_id, destination_url=url, deleted_at=None).exists()


def store(link_id: str, url: str, values: dict | None, *, error: str | None = None) -> bool:
    """Store a fetch's result, only if the link still has `url` and isn't deleted (a URL edit
    or a deletion during the fetch discards it). `values` None means the fetch failed: that
    replaces earlier failures and pending states, but never good values for the same URL.
    Returns whether a row was written."""
    if values is not None:
        metadata = {"link_url": url, "status": READY, **values, "error": None}
    else:
        metadata = {"link_url": url, "status": UNAVAILABLE, "error": error}
    rows = SharedLink.objects.filter(pk=link_id, destination_url=url, deleted_at=None)
    if values is None:
        # Containment (@>), not key comparisons: a missing key compares as NULL, and NOT NULL
        # would also skip links with no metadata at all.
        rows = rows.exclude(metadata__contains={"link_url": url, "status": READY})
    # A bare UPDATE: no updated_at, no revision. Metadata isn't content.
    return rows.update(metadata=metadata, metadata_fetched_at=timezone.now()) > 0


@transaction.atomic
def refresh(principal: Principal, list_id: UUID, link_id: UUID) -> None:
    """Fetch a link's page again (editors), at most once per link per REFRESH_INTERVAL."""
    from .links import get_live_link  # links imports this module

    locked, actor, facts = _lock(principal, list_id)
    if not can(actor, Action.EDIT, facts):
        raise denied(principal, "You can't change this list.")
    link = get_live_link(locked, link_id)
    if not settings.METADATA_FETCH_ENABLED:
        raise errors.Conflict(
            "Fetching details is turned off on this server.", code="metadata_disabled"
        )
    # cache.add is atomic in the database cache: two refreshes at once can't both pass.
    if not cache.add(f"metadata-refresh:{link.pk}", True, timeout=REFRESH_INTERVAL):
        raise Throttled(
            wait=REFRESH_INTERVAL, detail="Details were refreshed recently. Try again later."
        )
    request_fetch(link.pk, link.destination_url)
