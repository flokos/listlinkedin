"""List operations for /api/v2/: account ownership, visibility and settings.

Authorization is decided by the policy, and re-decided after the list's row lock is taken:
a request that was allowed before a concurrent change (token rotated or claimed, membership
removed, visibility changed) can't commit after it (docs/v2/12-AUTHORIZATION.md).
"""

import logging
from datetime import datetime
from uuid import UUID

from django.db import IntegrityError, transaction

from apps.common import errors
from apps.shortener.services import create_with_unique_code
from apps.versioning.models import RevisionKind
from apps.versioning.services import record_revision

from .. import tokens
from ..domain import slug_for
from ..models import CREATION_KEY_CONSTRAINT, OWNER_ACTIVE, PUBLIC_CODE_CONSTRAINT, SharedList
from ..policy import Action, Actor, ListFacts, Visibility, can, can_set_visibility
from ..selectors import Principal, actor_for, facts_for

logger = logging.getLogger(__name__)

CONTENT_FIELDS = ("title", "description")
SETTINGS_FIELDS = ("visibility", "allow_fork", "allow_branch", "expires_at")
TAG_FIELDS = ("tags",)  # editors and owners, not versioned (docs/v2/12-AUTHORIZATION.md)

VERIFY_EMAIL_TO_PUBLISH = "Verify your email address to make lists public."


@transaction.atomic
def create_list(
    principal: Principal,
    *,
    title: str,
    description: str = "",
    visibility: Visibility = Visibility.PRIVATE,
    allow_fork: bool = False,
    allow_branch: bool = False,
    expires_at: datetime | None = None,
    creation_key: UUID | None = None,
) -> tuple[SharedList, bool]:
    """Create a list owned by the signed-in user. Returns (list, created).

    With a `creation_key` (the request's Idempotency-Key), repeating the request returns the
    list the first one created instead of a second list.
    """
    user = principal.user
    if user is None:
        raise errors.AuthenticationRequired("Sign in to create lists.")
    if visibility is Visibility.PUBLIC and not principal.email_verified:
        raise errors.Forbidden(VERIFY_EMAIL_TO_PUBLISH)
    if creation_key is not None and (existing := _created_with(creation_key, user)):
        return existing, False

    try:
        shared_list = create_with_unique_code(
            lambda code: SharedList.objects.create(
                public_code=code,
                owner=user,
                title=title,
                slug=slug_for(title),
                description=description,
                visibility=visibility.value,
                allow_fork=allow_fork,
                allow_branch=allow_branch,
                expires_at=expires_at,
                creation_key=creation_key,
            ),
            PUBLIC_CODE_CONSTRAINT,
        )
    except IntegrityError as exc:
        # The same key, concurrently: the other request won. Answer with its list.
        if _violated_constraint(exc) != CREATION_KEY_CONSTRAINT:
            raise
        return _created_with(creation_key, user), False
    # Revision 1, in the creating transaction (docs/v2/07-REVISION-SPEC.md#numbering).
    record_revision(_relock(shared_list), kind=RevisionKind.CREATED, user=user)
    logger.info("Created list %s", shared_list.id)
    return shared_list, True


def _created_with(creation_key: UUID, user) -> SharedList | None:
    existing = SharedList.objects.filter(creation_key=creation_key).first()
    if existing is not None and existing.owner_id != user.pk:
        raise errors.Conflict(
            "This Idempotency-Key was already used.", code="idempotency_key_reused"
        )
    return existing


def _violated_constraint(exc: IntegrityError) -> str | None:
    return getattr(getattr(exc.__cause__, "diag", None), "constraint_name", None)


@transaction.atomic
def update_list(
    principal: Principal, list_id: UUID, changes: dict, *, expected_head: int | None = None
) -> SharedList:
    """Apply validated changes. Content (title, description) needs edit rights and is
    versioned; settings (visibility, fork/branch permission, expiry) need the owner and
    aren't. `expected_head` (the request's If-Match) applies to content changes only."""
    locked, actor, facts = _lock(principal, list_id, with_email="visibility" in changes)
    content = any(f in changes for f in CONTENT_FIELDS)
    if content and not can(actor, Action.EDIT, facts):
        raise denied(principal, "You can't change this list.")
    if content:
        check_head(locked, expected_head)
    if any(f in changes for f in SETTINGS_FIELDS) and not can(actor, Action.SETTINGS, facts):
        raise denied(principal, "Only the list's owner can change its settings.")
    if any(f in changes for f in TAG_FIELDS) and not can(actor, Action.TAGS, facts):
        raise denied(principal, "Only the list's owner and editors can change its tags.")
    if "visibility" in changes and not can_set_visibility(
        actor, facts, Visibility(changes["visibility"])
    ):
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
    if content:
        record_revision(locked, kind=RevisionKind.EDITED, user=principal.user)
    return locked


@transaction.atomic
def delete_lists_owned_by(user) -> int:
    """Delete every list `user` owns, when their account is deleted
    (docs/v2/04-DOMAIN-MODEL.md#ownership-rules).

    The rows are locked first, in id order like every multi-list write, so a write in progress
    on one of them finishes before its list goes. Links, short URLs and memberships cascade.
    """
    ids = list(
        SharedList.objects.select_for_update()
        .filter(owner=user)
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    SharedList.objects.filter(pk__in=ids).delete()
    logger.info("Deleted %d lists owned by user %s", len(ids), user.pk)
    return len(ids)


@transaction.atomic
def delete_list(principal: Principal, list_id: UUID) -> None:
    locked, actor, facts = _lock(principal, list_id)
    if not can(actor, Action.DELETE, facts):
        raise denied(principal, "Only the list's owner can delete it.")
    locked.delete()  # cascades to links, redirects and memberships
    logger.info("Deleted list %s", list_id)


@transaction.atomic
def rotate_owner_token(principal: Principal, list_id: UUID) -> str:
    """Replace a legacy list's owner token; the old one stops working at once (V1 behaviour)."""
    locked, actor, facts = _lock(principal, list_id)
    if not can(actor, Action.ROTATE_TOKEN, facts):
        raise denied(principal, "Only the holder of this list's edit link can replace it.")
    owner_token = tokens.generate_owner_token()
    locked.owner_token_hash = tokens.hash_owner_token(owner_token)
    locked.save(update_fields=["owner_token_hash", "updated_at"])
    logger.info("Rotated owner token of list %s", locked.id)
    return owner_token


@transaction.atomic
def claim_list(principal: Principal, list_id: UUID) -> SharedList:
    """Make the signed-in user the owner of a legacy list whose owner token they present.

    The token is retired in the same transaction, so it can't be used again by anyone. The
    list's visibility (unlisted) and expiry don't change; making it permanent is a separate,
    explicit choice. Claiming a list you already own is a no-op (idempotent).
    """
    if principal.user is None:
        raise errors.AuthenticationRequired("Sign in to add this list to your account.")
    locked = SharedList.objects.select_for_update().filter(pk=list_id).first()
    if locked is not None and locked.owner_id == principal.user.pk:
        return locked
    locked, actor, facts = _lock(principal, list_id)
    if not can(actor, Action.CLAIM, facts):
        raise errors.Forbidden("This edit link doesn't work for this list any more.")
    locked.owner = principal.user
    locked.owner_token_hash = None
    locked.save(update_fields=["owner", "owner_token_hash", "updated_at"])
    logger.info("List %s claimed by user %s", locked.id, principal.user.pk)
    return locked


def check_head(locked: SharedList, expected_head: int | None) -> None:
    """The If-Match precondition: the client's change was based on revision `expected_head`.
    Checked under the lock, so a write that landed in between is always noticed."""
    if expected_head is not None and expected_head != locked.head_revision:
        raise errors.RevisionMismatch(
            "This list changed since you loaded it. Reload to see the latest version.",
            head_revision=locked.head_revision,
        )


def _relock(shared_list: SharedList) -> SharedList:
    return SharedList.objects.select_for_update(of=("self",)).get(pk=shared_list.pk)


def denied(principal: Principal, message: str) -> errors.DomainError:
    """The error for a refused action: 401 for an anonymous caller, who may be allowed once
    signed in (V1's 401 vs 403 split, docs/v2/12-AUTHORIZATION.md#status-codes), else 403."""
    if principal.user is None and principal.token is None:
        return errors.AuthenticationRequired(message)
    return errors.Forbidden(message)


def lock_list(principal: Principal, list_id: UUID) -> tuple[SharedList, Actor, ListFacts]:
    """Lock a list the principal may view and return who they are on it, for another app's
    write that depends on the list (adding it to a group). 404 if not viewable, 410 if
    expired."""
    return _lock(principal, list_id)


def _lock(
    principal: Principal, list_id: UUID, *, with_email: bool = False
) -> tuple[SharedList, Actor, ListFacts]:
    """Lock the list row and decide who the principal is on it *now*."""
    # The owner is joined to check OWNER_ACTIVE; only the list row is locked.
    locked = (
        SharedList.objects.select_for_update(of=("self",)).filter(OWNER_ACTIVE, pk=list_id).first()
    )
    if locked is None:
        raise errors.NotVisible()
    actor = actor_for(principal, locked, with_email=with_email)
    facts = facts_for(principal, locked)
    if not can(actor, Action.VIEW, facts):
        raise errors.NotVisible()
    if locked.is_expired:
        raise errors.Expired("This list has expired.")
    return locked, actor, facts
