"""Link operations for /api/v2/, authorized by the policy (editors, owners, or a legacy
list's owner token). The rules are V1's: at most 100 links, no duplicate URLs, the short
code never changes. Positions and soft deletion arrive with task 2.1."""

from uuid import UUID

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.shortener.services import create_redirect

from ..domain import MAX_LINKS_PER_LIST
from ..models import SharedLink
from ..policy import Action, can
from ..selectors import Principal
from .legacy import _ensure_not_duplicate, _get_link
from .lists import _lock, denied


def _lock_for_edit(principal: Principal, list_id: UUID):
    locked, actor, facts = _lock(principal, list_id)
    if not can(actor, Action.EDIT, facts):
        raise denied(principal, "You can't change this list.")
    return locked


@transaction.atomic
def add_link(
    principal: Principal, list_id: UUID, *, destination_url: str, title: str | None = None
) -> SharedLink:
    locked = _lock_for_edit(principal, list_id)
    if locked.links.count() >= MAX_LINKS_PER_LIST:
        raise ValidationError(f"A list can contain at most {MAX_LINKS_PER_LIST} links.")
    _ensure_not_duplicate(locked, destination_url)
    link = SharedLink.objects.create(
        shared_list=locked, destination_url=destination_url, title=title
    )
    create_redirect(link)
    return link


@transaction.atomic
def update_link(principal: Principal, list_id: UUID, link_id: UUID, changes: dict) -> SharedLink:
    """The link keeps its id and short code when its URL changes (K1)."""
    locked = _lock_for_edit(principal, list_id)
    link = _get_link(locked, link_id)
    new_destination = changes.get("destination_url")
    if new_destination is not None and new_destination != link.destination_url:
        _ensure_not_duplicate(locked, new_destination)
    for field, value in changes.items():
        setattr(link, field, value)
    link.save(update_fields=[*changes, "updated_at"])
    return link


@transaction.atomic
def delete_link(principal: Principal, list_id: UUID, link_id: UUID) -> None:
    locked = _lock_for_edit(principal, list_id)
    _get_link(locked, link_id).delete()  # cascades to its short URL
