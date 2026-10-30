from dataclasses import dataclass, field
from functools import cached_property

from allauth.account.utils import has_verified_email
from django.conf import settings
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
from rest_framework.exceptions import NotFound

from apps.common import errors
from apps.shortener.models import ShortRedirect

from .exceptions import Gone
from .models import OWNER_ACTIVE, ListMembership, SharedLink, SharedList
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
        .filter(OWNER_ACTIVE, public_code=code)
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


def list_id_of(code: str):
    """The id of the list with this public code, or None. Says nothing about who may see it:
    callers lock the list with `services.lists.lock_list`, which decides."""
    return SharedList.objects.filter(public_code=code).values_list("pk", flat=True).first()


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
        .filter(OWNER_ACTIVE)
        .select_related("owner")
        .annotate(
            member_role=Subquery(membership.values("role")[:1]),
            link_count=Coalesce(Subquery(link_count), Value(0), output_field=IntegerField()),
        )
        .order_by("-updated_at", "-pk")
    )


def access_in_listing(user, shared_list: SharedList) -> Access:
    """Access for a row annotated with the user's `member_role` (`lists_of(user)`, or a
    group's lists), from its annotations (no extra queries). `user` may be None (signed out).
    """
    actor = Actor(user_id=user.pk if user is not None else None)
    role = shared_list.member_role
    is_owner = user is not None and shared_list.owner_id == user.pk
    facts = ListFacts(
        id=shared_list.pk,
        owner_id=shared_list.owner_id,
        visibility=Visibility(shared_list.visibility),
        allow_fork=shared_list.allow_fork,
        allow_branch=shared_list.allow_branch,
        member_role=Role(role) if role and not is_owner else None,
    )
    return Access(actor, facts)


def fork_sources(user, lists) -> dict:
    """For lists that are copies (forks), the lists they were copied from, as `user` (None:
    signed out) sees them: {source id: {"code", "title"}} for each source the user may view
    now. A source that was deleted, has expired, or isn't viewable is left out, so a copy never
    reveals a list its reader can't open. One query for all of `lists`."""
    ids = {lst.forked_from_id for lst in lists if lst.forked_from_id is not None}
    if not ids:
        return {}
    role = (
        Subquery(
            ListMembership.objects.filter(shared_list=OuterRef("pk"), user=user).values("role")[:1]
        )
        if user is not None
        else Value(None, output_field=CharField())
    )
    sources = (
        SharedList.objects.filter(OWNER_ACTIVE, pk__in=ids)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=Now()))
        .annotate(member_role=role)
    )
    shown = {}
    for source in sources:
        access = access_in_listing(user, source)
        if can_view(access.actor, access.facts):
            shown[source.pk] = {"code": source.public_code, "title": source.title}
    return shown


def members_of(shared_list: SharedList, access: Access) -> QuerySet[ListMembership]:
    """The people a list is shared with, oldest first. Only the owner and editors may see
    them (docs/v2/09-API-DESIGN.md#lists); everyone else gets 403."""
    if not can(access.actor, Action.VIEW_MEMBERS, access.facts):
        raise errors.Forbidden("Only the owner and editors can see who this list is shared with.")
    return (
        ListMembership.objects.filter(shared_list=shared_list, user__deleted_at__isnull=True)
        .select_related("user")
        .order_by("created_at", "pk")
    )


# V1 (/api/v1/) reads.


def get_active_list(public_code: str) -> SharedList:
    """Return a non-expired list for the V1 API. Unknown codes raise 404, expired ones 410.

    V1 has no sign-in, so it sees only lists anyone with the URL may see: private lists
    answer 404 exactly like unknown ones.
    """
    shared_list = SharedList.objects.filter(OWNER_ACTIVE, public_code=public_code).first()
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


def media_in_use() -> set[str]:
    """Every media path a list or link refers to, for `cleanup_media`: list images, uploaded
    icons, and fetched icons and preview images (since 7.3). Tombstoned links count: restoring
    one brings its icon back. `cleanup_media` adds group images and the icons in revision
    snapshots."""
    images = SharedList.objects.exclude(image=None).values_list("image", flat=True)
    icons = SharedLink.objects.exclude(icon=None).values_list("icon", flat=True)
    fetched = set()
    for key in ("icon", "image"):
        fetched |= set(
            SharedLink.objects.filter(**{f"metadata__{key}__isnull": False})
            .values_list(f"metadata__{key}", flat=True)
            .distinct()
        )
    return {*images, *icons, *(path for path in fetched if path)}


# Fetched metadata (apps.sharing.services.metadata).


def current_metadata(link: SharedLink) -> dict | None:
    """The fetched values of a link, if its last finished fetch succeeded *for its current
    URL*. After a URL change, the old page's values never show."""
    fetched = link.metadata or {}
    if fetched.get("link_url") == link.destination_url and fetched.get("status") == "ready":
        return fetched
    return None


def metadata_status(link: SharedLink) -> str:
    """`ready` or `unavailable` (the last fetch of the current URL), else `pending` (a fetch
    is queued or running) or `disabled` (fetching is off on this server)."""
    fetched = link.metadata or {}
    if fetched.get("link_url") == link.destination_url and fetched.get("status") in (
        "ready",
        "unavailable",
    ):
        return fetched["status"]
    return "pending" if settings.METADATA_FETCH_ENABLED else "disabled"


def live_content(shared_list: SharedList) -> dict:
    """A list's versioned content as plain data, for its revision snapshot (apps.versioning):
    title, description and the live links in their stored order with their user fields."""
    links = SharedLink.objects.filter(shared_list=shared_list, deleted_at__isnull=True).order_by(
        "position"
    )
    return {
        "title": shared_list.title,
        "description": shared_list.description,
        "links": [
            {
                "id": link.pk,
                "source_link_id": link.source_link_id,
                "url": link.destination_url,
                "title": link.title,
                "description": link.description,
                "icon": link.icon,
            }
            for link in links
        ],
    }


def head_revision_of(shared_list: SharedList) -> int:
    """The list's current head revision, e.g. after a write the caller's copy predates."""
    return SharedList.objects.values_list("head_revision", flat=True).get(pk=shared_list.pk)
