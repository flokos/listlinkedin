"""Link operations (docs/v2/04-DOMAIN-MODEL.md#link-sharingsharedlink).

The rules are V1's: at most 100 live links, no duplicate live URLs, the short code never
changes (K1). V2 adds a stored order and tombstones:

- Live links have positions exactly 0..n-1 (K3). New links are appended, or inserted at a
  given position with the ones after it shifted down.
- Deleting a link keeps its row as a tombstone (`deleted_at` set, `position` NULL), so its id
  and short code survive for history and restore; its short URL answers 404. The positions
  after it close the gap.
- Reordering is a *move* of one link to an index, applied to the current order under the
  lock (docs/v2/adr/ADR-005), so concurrent moves never overwrite each other.
- A link never changes list (K4): "move to another list" copies it there and tombstones it
  here, in one transaction.

The `*_on` functions work on a list the caller has already locked and authorized; both the
v2 path below (policy, `Principal`) and the V1 owner-token path (`legacy`) call them. Their
callers record the revision (apps.versioning) after them, under the same lock, and check the
optional If-Match precondition (`expected_head`) before them.
"""

from uuid import UUID

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.shortener.services import create_redirect
from apps.versioning.models import RevisionKind
from apps.versioning.services import record_revision

from ..domain import MAX_LINKS_PER_LIST
from ..models import SharedLink, SharedList
from ..policy import Action, can
from ..selectors import Principal
from .lists import _lock, check_head, denied

DUPLICATE_URL = "This URL is already in the list."


# v2: authorized by the policy (editors, owners, or a legacy list's owner token).


def _lock_for_edit(
    principal: Principal, list_id: UUID, expected_head: int | None = None
) -> SharedList:
    locked, actor, facts = _lock(principal, list_id)
    if not can(actor, Action.EDIT, facts):
        raise denied(principal, "You can't change this list.")
    check_head(locked, expected_head)
    return locked


def _versioned(locked: SharedList, principal: Principal) -> None:
    record_revision(locked, kind=RevisionKind.EDITED, user=principal.user)


@transaction.atomic
def add_link(
    principal: Principal,
    list_id: UUID,
    *,
    destination_url: str,
    title: str | None = None,
    description: str | None = None,
    position: int | None = None,
    creation_key: UUID | None = None,
    expected_head: int | None = None,
) -> tuple[SharedLink, bool]:
    """Returns (link, created). Retrying with the same `creation_key` returns the first link."""
    locked = _lock_for_edit(principal, list_id)
    if creation_key is not None:
        existing = locked.links.filter(creation_key=creation_key).first()
        if existing is not None:
            return existing, False  # a retry: answered before the precondition, which moved
    check_head(locked, expected_head)
    link = add_link_on(
        locked,
        destination_url=destination_url,
        title=title,
        description=description,
        position=position,
        creation_key=creation_key,
    )
    _versioned(locked, principal)
    return link, True


@transaction.atomic
def update_link(
    principal: Principal,
    list_id: UUID,
    link_id: UUID,
    changes: dict,
    *,
    expected_head: int | None = None,
) -> SharedLink:
    locked = _lock_for_edit(principal, list_id, expected_head)
    link = update_link_on(locked, link_id, changes)
    _versioned(locked, principal)
    return link


@transaction.atomic
def delete_link(
    principal: Principal, list_id: UUID, link_id: UUID, *, expected_head: int | None = None
) -> None:
    locked = _lock_for_edit(principal, list_id, expected_head)
    delete_link_on(locked, link_id)
    _versioned(locked, principal)


@transaction.atomic
def move_link(
    principal: Principal,
    list_id: UUID,
    link_id: UUID,
    to_index: int,
    *,
    expected_head: int | None = None,
) -> bool:
    """Move a link to `to_index` (0-based, clamped). Returns False if nothing moved.

    No precondition is needed for a move (it applies to the current order), but one is
    honoured if sent."""
    locked = _lock_for_edit(principal, list_id, expected_head)
    moved = move_link_on(locked, link_id, to_index)
    if moved:
        _versioned(locked, principal)
    return moved


@transaction.atomic
def move_link_to_list(
    principal: Principal,
    source_id: UUID,
    link_id: UUID,
    target_id: UUID,
    *,
    expected_head: int | None = None,
) -> SharedLink:
    """Copy the link to the end of another list (new short URL) and delete it here (K4).

    Needs edit rights on both lists. Both rows are locked in ascending id order, like every
    multi-list write, so two moves in opposite directions can't deadlock.
    """
    if source_id == target_id:
        raise ValidationError({"list": ["The link is already in this list."]})
    locked = {}
    for list_id in sorted((source_id, target_id)):
        locked[list_id] = _lock(principal, list_id)  # NotVisible for a list you can't see
    source, source_actor, source_facts = locked[source_id]
    target, target_actor, target_facts = locked[target_id]
    if not can(source_actor, Action.EDIT, source_facts):
        raise denied(principal, "You can't change this list.")
    if not can(target_actor, Action.EDIT, target_facts):
        raise denied(principal, "You can't add links to that list.")
    check_head(source, expected_head)  # the list the user was looking at
    link = get_live_link(source, link_id)
    copy = add_link_on(
        target,
        destination_url=link.destination_url,
        title=link.title,
        description=link.description,
    )
    copy.icon, copy.metadata, copy.metadata_fetched_at = (
        link.icon,
        link.metadata,
        link.metadata_fetched_at,
    )
    copy.save(update_fields=["icon", "metadata", "metadata_fetched_at"])
    delete_link_on(source, link.pk)
    _versioned(target, principal)  # one revision in each list
    _versioned(source, principal)
    return copy


# Shared operations on a locked list.


def live_links(shared_list: SharedList):
    return shared_list.links.filter(deleted_at__isnull=True)


def add_link_on(
    locked: SharedList,
    *,
    destination_url: str,
    title: str | None = None,
    description: str | None = None,
    position: int | None = None,
    creation_key: UUID | None = None,
) -> SharedLink:
    count = live_links(locked).count()
    if count >= MAX_LINKS_PER_LIST:
        raise ValidationError(f"A list can contain at most {MAX_LINKS_PER_LIST} links.")
    _ensure_not_duplicate(locked, destination_url)
    at = count if position is None else max(0, min(position, count))
    if at < count:
        # The position constraint is deferred, so shifting in one statement is safe.
        live_links(locked).filter(position__gte=at).update(position=F("position") + 1)
    link = SharedLink.objects.create(
        shared_list=locked,
        destination_url=destination_url,
        title=title,
        description=description,
        position=at,
        creation_key=creation_key,
    )
    create_redirect(link)
    return link


def update_link_on(locked: SharedList, link_id: UUID, changes: dict) -> SharedLink:
    """The link keeps its id and short code when its URL changes (K1)."""
    link = get_live_link(locked, link_id)
    new_destination = changes.get("destination_url")
    if new_destination is not None and new_destination != link.destination_url:
        _ensure_not_duplicate(locked, new_destination)
    for field, value in changes.items():
        setattr(link, field, value)
    link.save(update_fields=[*changes, "updated_at"])
    return link


def delete_link_on(locked: SharedList, link_id: UUID) -> None:
    """Tombstone the link and close the gap in the positions after it."""
    link = get_live_link(locked, link_id)
    gap = link.position
    link.deleted_at = timezone.now()
    link.position = None
    link.save(update_fields=["deleted_at", "position", "updated_at"])
    live_links(locked).filter(position__gt=gap).update(position=F("position") - 1)


def move_link_on(locked: SharedList, link_id: UUID, to_index: int) -> bool:
    link = get_live_link(locked, link_id)
    last = live_links(locked).count() - 1
    to, at = max(0, min(to_index, last)), link.position
    if to == at:
        return False
    # Shift only the links between the old and new place; the position constraint is
    # deferred, so the temporary duplicates are fine until commit.
    if to > at:
        live_links(locked).filter(position__gt=at, position__lte=to).update(
            position=F("position") - 1
        )
    else:
        live_links(locked).filter(position__gte=to, position__lt=at).update(
            position=F("position") + 1
        )
    link.position = to
    link.save(update_fields=["position", "updated_at"])
    return True


def get_live_link(shared_list: SharedList, link_id: UUID) -> SharedLink:
    # Scoped to the list, so a link id from another list, or a deleted one, is "not found".
    link = live_links(shared_list).filter(pk=link_id).first()
    if link is None:
        raise NotFound()
    return link


def _ensure_not_duplicate(shared_list: SharedList, destination_url: str) -> None:
    if live_links(shared_list).filter(destination_url=destination_url).exists():
        raise ValidationError({"destination_url": [DUPLICATE_URL]})
