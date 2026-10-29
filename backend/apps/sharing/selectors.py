from dataclasses import dataclass, field
from functools import cached_property

from allauth.account.utils import has_verified_email
from django.db.models import (
    Case,
    Count,
    Exists,
    IntegerField,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from rest_framework.exceptions import NotFound

from apps.common import errors
from apps.shortener.models import ShortRedirect

from .exceptions import Gone
from .models import ListMembership, SharedLink, SharedList
from .policy import Action, Actor, ListFacts, Role, Visibility, can, can_view
from .tokens import verify_owner_token


@dataclass
class Principal:
    """Who is making a request, before any list is involved: the signed-in user (if any) and
    the bearer token presented (if any, not yet verified against anything)."""

    user: object | None = None
    token: str | None = field(default=None, repr=False)

    @cached_property
    def email_verified(self) -> bool:
        return self.user is not None and has_verified_email(self.user)


ANONYMOUS = Principal()


def actor_for(principal: Principal, shared_list: SharedList, *, with_email: bool = False) -> Actor:
    """The policy's view of `principal` on this list. The token counts only if it is this
    list's own (constant-time check), so it can never reach another list (A3)."""
    holds_token = principal.token is not None and verify_owner_token(
        principal.token, shared_list.owner_token_hash
    )
    return Actor(
        user_id=principal.user.pk if principal.user is not None else None,
        legacy_list_id=shared_list.pk if holds_token else None,
        email_verified=principal.email_verified if with_email else False,
    )


def facts_for(principal: Principal, shared_list: SharedList) -> ListFacts:
    role = None
    user = principal.user
    if user is not None and shared_list.owner_id != user.pk:
        role = (
            ListMembership.objects.filter(shared_list=shared_list, user=user)
            .values_list("role", flat=True)
            .first()
        )
    return ListFacts(
        id=shared_list.pk,
        owner_id=shared_list.owner_id,
        visibility=Visibility(shared_list.visibility),
        allow_fork=shared_list.allow_fork,
        allow_branch=shared_list.allow_branch,
        member_role=Role(role) if role else None,
    )


@dataclass(frozen=True)
class Access:
    """A list as one principal sees it: what the API needs for representations."""

    actor: Actor
    facts: ListFacts


def get_list_for(principal: Principal, code: str) -> tuple[SharedList, Access]:
    """A list the principal may view. Unknown and not-viewable answer the same 404, so private
    lists don't reveal that they exist (A2); expired lists the principal could see are 410."""
    shared_list = (
        SharedList.objects.select_related("owner")
        .annotate(link_count=Count("links", filter=Q(links__deleted_at__isnull=True)))
        .filter(public_code=code)
        .first()
    )
    if shared_list is None:
        raise errors.NotVisible()
    access = Access(actor_for(principal, shared_list), facts_for(principal, shared_list))
    if not can(access.actor, Action.VIEW, access.facts):
        raise errors.NotVisible()
    if shared_list.is_expired:
        raise errors.Expired("This list has expired.")
    return shared_list, access


def lists_of(user, *, role: Role | None = None) -> QuerySet[SharedList]:
    """Lists the user owns or is a member of ("My lists"), with their role and link count,
    optionally only those with one role. Unlisted lists of other people never appear here,
    even if the user has their URL."""
    membership = ListMembership.objects.filter(shared_list=OuterRef("pk"), user=user)
    link_count = (
        SharedLink.objects.filter(shared_list=OuterRef("pk"), deleted_at__isnull=True)
        .values("shared_list")
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
        SharedList.objects.filter(which)
        .select_related("owner")
        .annotate(
            member_role=Subquery(membership.values("role")[:1]),
            link_count=Coalesce(Subquery(link_count), Value(0), output_field=IntegerField()),
            is_owner=Case(When(owner=user, then=Value(1)), default=Value(0)),
        )
        .order_by("-updated_at", "-pk")
    )


def access_in_listing(user, shared_list: SharedList) -> Access:
    """Access for a row of `lists_of(user)`, from its annotations (no extra queries)."""
    actor = Actor(user_id=user.pk)
    role = shared_list.member_role
    facts = ListFacts(
        id=shared_list.pk,
        owner_id=shared_list.owner_id,
        visibility=Visibility(shared_list.visibility),
        allow_fork=shared_list.allow_fork,
        allow_branch=shared_list.allow_branch,
        member_role=Role(role) if role and not shared_list.is_owner else None,
    )
    return Access(actor, facts)


def members_of(shared_list: SharedList, access: Access) -> QuerySet[ListMembership]:
    """The people a list is shared with, oldest first. Only the owner and editors may see
    them (docs/v2/09-API-DESIGN.md#lists); everyone else gets 403."""
    if not can(access.actor, Action.VIEW_MEMBERS, access.facts):
        raise errors.Forbidden("Only the owner and editors can see who this list is shared with.")
    return (
        ListMembership.objects.filter(shared_list=shared_list)
        .select_related("user")
        .order_by("created_at", "pk")
    )


# V1 (/api/v1/) reads.


def get_active_list(public_code: str) -> SharedList:
    """Return a non-expired list for the V1 API. Unknown codes raise 404, expired ones 410.

    V1 has no sign-in, so it sees only lists anyone with the URL may see: private lists
    answer 404 exactly like unknown ones.
    """
    shared_list = SharedList.objects.filter(public_code=public_code).first()
    if shared_list is None or not can_view(Actor(), _anonymous_facts(shared_list)):
        raise NotFound()
    if shared_list.is_expired:
        raise Gone()
    return shared_list


def _anonymous_facts(shared_list: SharedList) -> ListFacts:
    return ListFacts(
        id=shared_list.pk,
        owner_id=shared_list.owner_id,
        visibility=Visibility(shared_list.visibility),
    )


def links_with_short_codes(
    shared_list: SharedList, *, newest_first: bool = False
) -> QuerySet[SharedLink]:
    """Live links of a list in their stored order, each annotated with its active
    `short_code`. Deleted links (tombstones) never appear. `newest_first` is the V1 API's
    order, kept as its contract."""
    active_code = ShortRedirect.objects.filter(link=OuterRef("pk"), is_active=True).values("code")
    order = ("-created_at", "-id") if newest_first else ("position",)
    return (
        SharedLink.objects.filter(shared_list=shared_list, deleted_at__isnull=True)
        .annotate(short_code=Subquery(active_code[:1]))
        .order_by(*order)
    )


def get_link(shared_list: SharedList, link_id) -> SharedLink:
    link = links_with_short_codes(shared_list).filter(pk=link_id).first()
    if link is None:
        raise NotFound()
    return link
