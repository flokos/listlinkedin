"""Reads of groups. These are the only way group querysets and the lists a group shows are
filtered (docs/v2/12-AUTHORIZATION.md#implementation-notes)."""

from dataclasses import dataclass

from django.db.models import Count, Exists, IntegerField, OuterRef, Q, QuerySet, Subquery, Value
from django.db.models.functions import Coalesce, Now

from apps.common import errors
from apps.sharing.models import ListMembership
from apps.sharing.policy import (
    Actor,
    GroupAction,
    GroupFacts,
    Role,
    Visibility,
    can_group,
)
from apps.sharing.selectors import Principal

from .models import GROUP_OWNER_ACTIVE, Group, GroupList, GroupMembership


@dataclass(frozen=True)
class GroupAccess:
    """A group as one principal sees it."""

    actor: Actor
    facts: GroupFacts


def group_actor(principal: Principal, *, with_email: bool = False) -> Actor:
    """Groups know no owner tokens: a legacy edit link grants nothing here."""
    return Actor(
        user_id=principal.user.pk if principal.user is not None else None,
        email_verified=principal.email_verified if with_email else False,
    )


def group_facts_for(principal: Principal, group: Group) -> GroupFacts:
    role = None
    user = principal.user
    if user is not None and group.owner_id != user.pk:
        role = (
            GroupMembership.objects.filter(group=group, user=user)
            .values_list("role", flat=True)
            .first()
        )
    return GroupFacts(
        id=group.pk,
        owner_id=group.owner_id,
        visibility=Visibility(group.visibility),
        member_role=Role(role) if role else None,
    )


def get_group_for(principal: Principal, code: str) -> tuple[Group, GroupAccess]:
    """A group the principal may view. Unknown and not viewable answer the same 404 (A2)."""
    group = Group.objects.select_related("owner").filter(GROUP_OWNER_ACTIVE, code=code).first()
    if group is None:
        raise errors.NotVisible()
    access = GroupAccess(group_actor(principal), group_facts_for(principal, group))
    if not can_group(access.actor, GroupAction.VIEW, access.facts):
        raise errors.NotVisible()
    return group, access


def shown_lists_q(user) -> Q:
    """`policy.shown_in_group` in SQL, on GroupList rows, for a viewer who can view the group.

    Lists nobody may open are never shown either: expired ones, and those whose owner is
    deleting their account.
    """
    rule = Q(shared_list__visibility=Visibility.PUBLIC.value) | (
        Q(shared_list__visibility=Visibility.UNLISTED.value)
        & ~Q(group__visibility=Visibility.PUBLIC.value)
    )
    if user is not None:
        member = ListMembership.objects.filter(shared_list=OuterRef("shared_list"), user=user)
        rule |= Q(shared_list__owner=user) | Q(Exists(member))
    live = (Q(shared_list__owner__isnull=True) | Q(shared_list__owner__deleted_at__isnull=True)) & (
        Q(shared_list__expires_at__isnull=True) | Q(shared_list__expires_at__gt=Now())
    )
    return rule & live


def entries_for(principal: Principal, group: Group) -> QuerySet[GroupList]:
    """The group's entries this principal is shown, in order. Everything else is omitted
    entirely, so counts and positions taken from this reveal nothing hidden."""
    return (
        GroupList.objects.filter(group=group)
        .filter(shown_lists_q(principal.user))
        .select_related("shared_list__owner")
        .order_by("position", "pk")
    )


def groups_of(user, *, role: Role | None = None) -> QuerySet[Group]:
    """Groups the user owns or is a member of, with their role and the number of lists the
    group shows *them*. Unlisted groups of other people never appear here."""
    membership = GroupMembership.objects.filter(group=OuterRef("pk"), user=user)
    shown = (
        GroupList.objects.filter(group=OuterRef("pk"))
        .filter(shown_lists_q(user))
        .values("group")
        .annotate(n=Count("pk"))
        .values("n")
    )
    if role is Role.OWNER:
        which = Q(owner=user)
    elif role is not None:
        which = Q(Exists(membership.filter(role=role.value)))
    else:
        which = Q(owner=user) | Q(Exists(membership))
    return (
        Group.objects.filter(which)
        .filter(GROUP_OWNER_ACTIVE)
        .select_related("owner")
        .annotate(
            member_role=Subquery(membership.values("role")[:1]),
            list_count=Coalesce(Subquery(shown), Value(0), output_field=IntegerField()),
        )
        .order_by("-updated_at", "-pk")
    )


def members_of(group: Group, access: GroupAccess) -> QuerySet[GroupMembership]:
    """The people a group is shared with, oldest first: for its owner and editors."""
    if not can_group(access.actor, GroupAction.VIEW_MEMBERS, access.facts):
        raise errors.Forbidden("Only the owner and editors can see who this group is shared with.")
    return (
        GroupMembership.objects.filter(group=group, user__deleted_at__isnull=True)
        .select_related("user")
        .order_by("created_at", "pk")
    )
