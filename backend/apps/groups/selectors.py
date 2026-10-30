"""Reads of groups. These are the only way group querysets and the lists a group shows are
filtered (docs/v2/12-AUTHORIZATION.md#implementation-notes)."""

from dataclasses import dataclass

from django.db import connection
from django.db.models import (
    CharField,
    Count,
    Exists,
    IntegerField,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Value,
)
from django.db.models.functions import Coalesce, Now

from apps.accounts.models import User
from apps.common import errors
from apps.sharing.models import ListMembership, SharedLink, SharedList
from apps.sharing.policy import (
    Actor,
    GroupAction,
    GroupFacts,
    Role,
    Visibility,
    can_group,
)
from apps.sharing.selectors import Principal, search_and_order

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


def facts_in_listing(user, group: Group) -> GroupFacts:
    """Facts for a row of `groups_of(user)`, from its annotations (no extra queries)."""
    role = group.member_role if user is not None and group.owner_id != user.pk else None
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


def lists_in(principal: Principal, group: Group) -> QuerySet[SharedList]:
    """The lists the group shows this principal, in the group's order, annotated like
    `sharing.selectors.lists_of` (`member_role`, `link_count`) so `access_in_listing` can
    describe each one. Stored positions stay inside: the order is all that comes out."""
    user = principal.user
    shown = entries_for(principal, group)
    entry = GroupList.objects.filter(group=group, shared_list=OuterRef("pk"))
    links = (
        SharedLink.objects.filter(shared_list=OuterRef("pk"), deleted_at__isnull=True)
        .values("shared_list")
        .annotate(n=Count("pk"))
        .values("n")
    )
    member_role = (
        Subquery(
            ListMembership.objects.filter(shared_list=OuterRef("pk"), user=user).values("role")[:1]
        )
        if user is not None
        else Value(None, output_field=CharField())
    )
    return (
        SharedList.objects.filter(pk__in=shown.values("shared_list"))
        .select_related("owner")
        .annotate(
            group_position=Subquery(entry.values("position")[:1]),
            member_role=member_role,
            link_count=Coalesce(Subquery(links), Value(0), output_field=IntegerField()),
        )
        .order_by("group_position", "pk")
    )


def media_in_use() -> set[str]:
    """Group images, for `cleanup_media`."""
    return set(Group.objects.exclude(image=None).values_list("image", flat=True))


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


# Discovery (phase 8): public groups, and the tag facets of lists and groups together.


def public_groups(user, *, q: str = "", tags: list[str] | None = None, ordering: str):
    """The directory of groups: `public`, owner not deleting their account. Annotated like
    `groups_of` (`member_role` for `user`, and `list_count`: the lists the group shows *this*
    viewer, so a count never reveals a hidden list)."""
    shown = (
        GroupList.objects.filter(group=OuterRef("pk"))
        .filter(shown_lists_q(user))
        .values("group")
        .annotate(n=Count("pk"))
        .values("n")
    )
    member_role = (
        Subquery(GroupMembership.objects.filter(group=OuterRef("pk"), user=user).values("role")[:1])
        if user is not None
        else Value(None, output_field=CharField())
    )
    groups = (
        Group.objects.filter(visibility=Visibility.PUBLIC.value)
        .filter(GROUP_OWNER_ACTIVE)
        .select_related("owner")
        .annotate(
            member_role=member_role,
            list_count=Coalesce(Subquery(shown), Value(0), output_field=IntegerField()),
        )
    )
    return search_and_order(groups, q, tags or [], ordering)


def popular_tags(prefix: str = "", *, limit: int = 30) -> list[tuple[str, int]]:
    """The most used tags on public lists and groups, as (tag, count), most used first.
    Only what the directory shows is counted: public, not expired, owner not leaving. Raw SQL
    because PostgreSQL won't group by `unnest(...)` the way the ORM writes it."""
    lists, groups, users = (
        SharedList._meta.db_table,
        Group._meta.db_table,
        User._meta.db_table,
    )
    sql = f"""
        SELECT tag, count(*) AS n FROM (
            SELECT unnest(l.tags) AS tag FROM {lists} l
            LEFT JOIN {users} u ON u.id = l.owner_id
            WHERE l.visibility = 'public' AND (l.owner_id IS NULL OR u.deleted_at IS NULL)
              AND (l.expires_at IS NULL OR l.expires_at > now())
            UNION ALL
            SELECT unnest(g.tags) FROM {groups} g
            JOIN {users} u ON u.id = g.owner_id
            WHERE g.visibility = 'public' AND u.deleted_at IS NULL
        ) t
        WHERE starts_with(tag, %s)
        GROUP BY tag ORDER BY n DESC, tag LIMIT %s
    """  # noqa: S608 (table names come from models; values are parameters)
    with connection.cursor() as cursor:
        cursor.execute(sql, [prefix, limit])
        return [(tag, n) for tag, n in cursor.fetchall()]
