"""Writes on groups (docs/v2/12-AUTHORIZATION.md#group-permission-matrix).

Every write locks the group row and re-decides authorization under the lock, like list
writes do, so a request allowed before a concurrent change (membership removed, visibility
changed) can't commit after it. Adding a list also locks the list, the two rows in ascending
id order (docs/v2/04-DOMAIN-MODEL.md#aggregates-and-consistency-boundaries).
"""

import logging
from uuid import UUID

from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.accounts.selectors import user_to_share_with
from apps.common import errors
from apps.metadata import images
from apps.sharing.domain import slug_for
from apps.sharing.policy import (
    Actor,
    GroupAction,
    GroupFacts,
    Role,
    Visibility,
    can_add_list,
    can_group,
    can_set_group_visibility,
)
from apps.sharing.selectors import Principal, list_id_of
from apps.sharing.services.lists import denied, lock_list
from apps.sharing.services.moderation import Reason, notify_operator
from apps.shortener.services import create_with_unique_code

from .models import (
    GROUP_CODE_CONSTRAINT,
    GROUP_OWNER_ACTIVE,
    Group,
    GroupList,
    GroupMembership,
)
from .selectors import entries_for, get_group_for, group_actor, group_facts_for

logger = logging.getLogger(__name__)

MAX_LISTS_PER_GROUP = 100
CONTENT_FIELDS = ("title", "description", "tags")  # edit rights (tags since 8.1)
SETTINGS_FIELDS = ("visibility",)

VERIFY_EMAIL_TO_PUBLISH = "Verify your email address to make groups public."
VERIFY_EMAIL_TO_SHARE = "Verify your email address to add people to your groups."
CANNOT_ADD = (
    "We couldn't add this person. They need an account with a verified email address: "
    "ask them to sign up, then try again."
)
NOT_IN_GROUP = "This list isn't in the group."
CANNOT_CHANGE_IMAGE = "Only the group's editors and owner can change its image."


@transaction.atomic
def create_group(
    principal: Principal,
    *,
    title: str,
    description: str = "",
    visibility: Visibility = Visibility.PRIVATE,
    tags: list[str] | None = None,
) -> Group:
    user = principal.user
    if user is None:
        raise errors.AuthenticationRequired("Sign in to create groups.")
    if visibility is Visibility.PUBLIC and not principal.email_verified:
        raise errors.Forbidden(VERIFY_EMAIL_TO_PUBLISH)
    group = create_with_unique_code(
        lambda code: Group.objects.create(
            code=code,
            owner=user,
            title=title,
            slug=slug_for(title),
            description=description,
            visibility=visibility.value,
            tags=tags or [],
        ),
        GROUP_CODE_CONSTRAINT,
    )
    logger.info("Created group %s", group.id)
    return group


@transaction.atomic
def update_group(principal: Principal, group_id: UUID, changes: dict) -> Group:
    """Title and description need edit rights; visibility needs the owner."""
    locked, actor, facts = _lock(principal, group_id, with_email="visibility" in changes)
    if any(f in changes for f in CONTENT_FIELDS) and not can_group(actor, GroupAction.EDIT, facts):
        raise denied(principal, "You can't change this group.")
    if "visibility" in changes:
        if not can_group(actor, GroupAction.SETTINGS, facts):
            raise denied(principal, "Only the group's owner can change who can see it.")
        if not can_set_group_visibility(actor, facts, Visibility(changes["visibility"])):
            raise errors.Forbidden(VERIFY_EMAIL_TO_PUBLISH)

    fields = []
    for name, value in changes.items():
        setattr(locked, name, value.value if isinstance(value, Visibility) else value)
        fields.append(name)
    if "title" in changes:
        locked.slug = slug_for(changes["title"])
        fields.append("slug")
    if fields:
        locked.save(update_fields=[*fields, "updated_at"])
    return locked


@transaction.atomic
def delete_group(principal: Principal, group_id: UUID) -> None:
    """Delete a group, its entries and its memberships. The lists in it are untouched."""
    locked, actor, facts = _lock(principal, group_id)
    if not can_group(actor, GroupAction.DELETE, facts):
        raise denied(principal, "Only the group's owner can delete it.")
    locked.delete()
    logger.info("Deleted group %s", group_id)


def set_group_image(principal: Principal, group_id: UUID, data: bytes | None) -> Group:
    """Replace the group's image with `data` (any accepted format), or remove it (None).

    As for list images (apps.sharing.services.media): permission is checked before decoding,
    so strangers can't fill the disk, and again under the lock; the decode happens outside it.
    """
    path = None
    if data is not None:
        with transaction.atomic():
            _lock_for_edit(principal, group_id, CANNOT_CHANGE_IMAGE)
        try:
            path = images.store(images.process(data, images.IMAGE), images.IMAGE)
        except images.ImageRejected as exc:
            raise ValidationError({"file": [str(exc)]}) from None
    with transaction.atomic():
        locked = _lock_for_edit(principal, group_id, CANNOT_CHANGE_IMAGE)
        locked.image = path
        locked.save(update_fields=["image", "updated_at"])
    return locked


def _lock_for_edit(principal: Principal, group_id: UUID, message: str) -> Group:
    locked, actor, facts = _lock(principal, group_id)
    if not can_group(actor, GroupAction.EDIT, facts):
        raise denied(principal, message)
    return locked


# The lists in a group.


@transaction.atomic
def add_list(principal: Principal, group_id: UUID, list_code: str) -> GroupList:
    """Append a list to the group. The actor must edit the group and be able to share the
    list themselves (`policy.can_add_list`)."""
    list_id = list_id_of(list_code)
    if list_id is None:
        raise errors.NotVisible()
    group_locked, list_locked = _lock_group_and_list(principal, group_id, list_id)
    # The group decides first: someone who can't add to it learns nothing about the list.
    if isinstance(group_locked, errors.DomainError):
        raise group_locked
    group, actor, group_facts = group_locked
    if not can_group(actor, GroupAction.ADD_LIST, group_facts):
        raise denied(principal, "You can't add lists to this group.")
    if isinstance(list_locked, errors.DomainError):
        raise list_locked
    shared_list, _, list_facts = list_locked
    if not can_add_list(actor, group_facts, list_facts):
        raise errors.Forbidden(
            "You can add your own lists, lists you can edit, and public lists.",
            code="cannot_share_list",
        )
    entries = _ordered(group)
    if any(entry.shared_list_id == shared_list.pk for entry in entries):
        raise errors.Conflict("This list is already in the group.", code="duplicate_list")
    if len(entries) >= MAX_LISTS_PER_GROUP:
        raise ValidationError(f"A group can contain at most {MAX_LISTS_PER_GROUP} lists.")
    _renumber(group, entries)
    entry = GroupList.objects.create(
        group=group, shared_list=shared_list, position=len(entries), added_by=principal.user
    )
    group.save(update_fields=["updated_at"])
    logger.info("List %s added to group %s", shared_list.pk, group.pk)
    return entry


@transaction.atomic
def remove_list(principal: Principal, group_id: UUID, list_code: str) -> None:
    """Take a list out of the group (the list itself is untouched). An entry the actor isn't
    shown answers 404, like one that isn't there."""
    locked, actor, facts = _lock(principal, group_id)
    if not can_group(actor, GroupAction.EDIT, facts):
        raise denied(principal, "You can't remove lists from this group.")
    entry = entries_for(principal, locked).filter(shared_list__public_code=list_code).first()
    if entry is None:
        raise errors.NotVisible(NOT_IN_GROUP)
    entry.delete()
    _renumber(locked, _ordered(locked))
    locked.save(update_fields=["updated_at"])
    logger.info("List %s removed from group %s", entry.shared_list_id, locked.pk)


@transaction.atomic
def move_list(principal: Principal, group_id: UUID, list_code: str, to_index: int) -> GroupList:
    """Move a list to `to_index` (0-based, clamped) in the order the actor sees. Entries
    hidden from the actor keep their places, so a move reveals nothing about them and never
    displaces them."""
    locked, actor, facts = _lock(principal, group_id)
    if not can_group(actor, GroupAction.EDIT, facts):
        raise denied(principal, "You can't reorder this group.")
    entries = _ordered(locked)
    shown_ids = set(entries_for(principal, locked).values_list("pk", flat=True))
    shown = [entry for entry in entries if entry.pk in shown_ids]
    moving = next((e for e in shown if e.shared_list.public_code == list_code), None)
    if moving is None:
        raise errors.NotVisible(NOT_IN_GROUP)
    shown.remove(moving)
    shown.insert(min(to_index, len(shown)), moving)  # clamped to the end, like links
    reordered = iter(shown)
    _renumber(locked, [next(reordered) if e.pk in shown_ids else e for e in entries])
    locked.save(update_fields=["updated_at"])
    return moving


def _ordered(group: Group) -> list[GroupList]:
    return list(
        GroupList.objects.filter(group=group)
        .select_related("shared_list")
        .order_by("position", "pk")
    )


def _renumber(group: Group, entries: list[GroupList]) -> None:
    """Give `entries` positions 0..n-1 in this order, closing gaps left by deleted lists.
    The position constraint is checked at commit, so the swaps can't collide midway."""
    changed = []
    for index, entry in enumerate(entries):
        if entry.position != index:
            entry.position = index
            changed.append(entry)
    GroupList.objects.bulk_update(changed, ["position"])


# People on a group.


@transaction.atomic
def add_member(principal: Principal, group_id: UUID, *, email: str, role: Role) -> GroupMembership:
    locked, actor, facts = _lock(principal, group_id, with_email=True)
    if not can_group(actor, GroupAction.MEMBERS, facts):
        raise denied(principal, "Only the group's owner can add people.")
    if not actor.email_verified:
        raise errors.Forbidden(VERIFY_EMAIL_TO_SHARE, code="email_unverified")
    user = user_to_share_with(email)
    if user is None:
        raise ValidationError({"email": [CANNOT_ADD]})
    if user.pk == locked.owner_id:
        raise ValidationError({"email": ["That's you. You own this group already."]})
    membership, created = GroupMembership.objects.get_or_create(
        group=locked, user=user, defaults={"role": role.value, "added_by": principal.user}
    )
    if not created:
        raise ValidationError({"email": ["This person is already in the group."]})
    logger.info("User %s added to group %s as %s", user.pk, locked.id, role.value)
    return membership


@transaction.atomic
def change_role(principal: Principal, group_id: UUID, user_id: UUID, role: Role) -> GroupMembership:
    locked, actor, facts = _lock(principal, group_id)
    if not can_group(actor, GroupAction.MEMBERS, facts):
        raise errors.Forbidden("Only the group's owner can change roles.")
    membership = _membership(locked, user_id)
    if membership.role != role.value:
        membership.role = role.value
        membership.save(update_fields=["role"])
        logger.info("User %s is now %s on group %s", user_id, role.value, locked.id)
    return membership


@transaction.atomic
def remove_member(principal: Principal, group_id: UUID, user_id: UUID) -> None:
    """The owner removes someone, or a member leaves (removes themselves)."""
    locked, actor, facts = _lock(principal, group_id)
    leaving = principal.user is not None and principal.user.pk == user_id
    if leaving and not can_group(actor, GroupAction.LEAVE, facts):
        raise errors.Forbidden("Owners can't leave their own group. Delete it instead.")
    if not leaving and not can_group(actor, GroupAction.MEMBERS, facts):
        raise errors.Forbidden("Only the group's owner can remove people.")
    _membership(locked, user_id).delete()
    logger.info("User %s removed from group %s", user_id, locked.id)


def _membership(group: Group, user_id: UUID) -> GroupMembership:
    membership = GroupMembership.objects.filter(group=group, user_id=user_id).first()
    if membership is None:
        raise errors.NotVisible("This person isn't in the group.")
    return membership


# Moderation (docs/v2/13-SECURITY.md#moderation). Reports go through the policy; the
# operator's actions run from management commands and don't (shell access authorizes them).


def report_group(principal: Principal, code: str, *, reason: Reason, details: str = "") -> None:
    """Tell the operator about a group. Anyone who can view it may, except its owner."""
    group, access = get_group_for(principal, code)
    if not can_group(access.actor, GroupAction.REPORT, access.facts):
        raise errors.Forbidden("You can't report your own group.")
    notify_operator(
        kind="group",
        title=group.title,
        url=f"{settings.PUBLIC_BASE_URL}/g/{group.code}/{group.slug}",
        code=group.code,
        visibility=group.visibility,
        owner=f"user {group.owner_id}",
        reporter=principal.user,
        reason=reason,
        details=details,
        actions=[
            f"python manage.py unpublish_group --reason '…' -- {group.code}",
            f"python manage.py delete_group --reason '…' --yes -- {group.code}",
            f"python manage.py suspend_account {group.owner_id} --reason '…' --unpublish",
        ],
        object_id=group.pk,
    )


@transaction.atomic
def unpublish_group(code: str, *, reason: str) -> Group:
    """Make a group private: only its owner and members can still open it."""
    locked = _lock_by_code(code)
    if locked.visibility != Visibility.PRIVATE.value:
        locked.visibility = Visibility.PRIVATE.value
        locked.save(update_fields=["visibility", "updated_at"])
    logger.info("Operator unpublished group %s: %s", locked.pk, reason)
    return locked


@transaction.atomic
def delete_group_by_operator(code: str, *, reason: str) -> None:
    """Delete a group, its entries and its memberships. The lists in it are untouched."""
    locked = _lock_by_code(code)
    group_id = locked.pk
    locked.delete()
    logger.info("Operator deleted group %s: %s", group_id, reason)


@transaction.atomic
def make_groups_private_owned_by(user) -> int:
    """Unpublish every public or unlisted group the user owns (suspending an account)."""
    ids = list(
        Group.objects.select_for_update()
        .filter(owner=user)
        .exclude(visibility=Visibility.PRIVATE.value)
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    for group in Group.objects.filter(pk__in=ids):
        group.visibility = Visibility.PRIVATE.value
        group.save(update_fields=["visibility", "updated_at"])
    return len(ids)


def _lock_by_code(code: str) -> Group:
    locked = Group.objects.select_for_update().filter(code=code).first()
    if locked is None:
        raise errors.NotVisible(f"There is no group with the code {code}.")
    return locked


# Account erasure (apps.accounts.services.purge_account).


@transaction.atomic
def delete_groups_owned_by(user) -> int:
    """Delete every group `user` owns. The rows are locked first, in id order."""
    ids = list(
        Group.objects.select_for_update()
        .filter(owner=user)
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    Group.objects.filter(pk__in=ids).delete()
    logger.info("Deleted %d groups owned by user %s", len(ids), user.pk)
    return len(ids)


@transaction.atomic
def remove_group_memberships_of(user) -> int:
    """Take a user out of every group they were added to. The groups are locked first."""
    memberships = GroupMembership.objects.filter(user=user)
    group_ids = sorted(memberships.values_list("group_id", flat=True))
    if group_ids:
        list(
            Group.objects.select_for_update()
            .filter(pk__in=group_ids)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
    removed, _ = memberships.delete()
    return removed


def _lock(
    principal: Principal, group_id: UUID, *, with_email: bool = False
) -> tuple[Group, Actor, GroupFacts]:
    """Lock the group row and decide who the principal is on it *now*."""
    locked = (
        Group.objects.select_for_update(of=("self",))
        .filter(GROUP_OWNER_ACTIVE, pk=group_id)
        .first()
    )
    if locked is None:
        raise errors.NotVisible()
    actor = group_actor(principal, with_email=with_email)
    facts = group_facts_for(principal, locked)
    if not can_group(actor, GroupAction.VIEW, facts):
        raise errors.NotVisible()
    return locked, actor, facts


def _lock_group_and_list(principal: Principal, group_id: UUID, list_id: UUID):
    """Lock both rows in ascending id order (no deadlock with a writer locking them the other
    way round). Each result is the lock's outcome or the error it raised, so the caller can
    report refusals in a fixed order whatever order the rows were locked in."""
    steps = {
        "group": lambda: _lock(principal, group_id),
        "list": lambda: lock_list(principal, list_id),
    }
    order = ("list", "group") if list_id < group_id else ("group", "list")
    results: dict = {}
    for name in order:
        try:
            results[name] = steps[name]()
        except errors.DomainError as exc:
            results[name] = exc
    return results["group"], results["list"]
