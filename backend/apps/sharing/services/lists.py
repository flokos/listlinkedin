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

from .. import tokens
from ..domain import slug_for
from ..models import CREATION_KEY_CONSTRAINT, PUBLIC_CODE_CONSTRAINT, SharedList
from ..policy import Action, Actor, ListFacts, Visibility, can, can_set_visibility
from ..selectors import Principal, actor_for, facts_for

logger = logging.getLogger(__name__)

CONTENT_FIELDS = ("title", "description")
SETTINGS_FIELDS = ("visibility", "allow_fork", "allow_branch", "expires_at")

VERIFY_EMAIL_TO_PUBLISH = "Verify your email address to make lists public."


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
def update_list(principal: Principal, list_id: UUID, changes: dict) -> SharedList:
    """Apply validated changes. Content (title, description) needs edit rights; settings
    (visibility, fork/branch permission, expiry) need the owner."""
    locked, actor, facts = _lock(principal, list_id, with_email="visibility" in changes)
    if any(f in changes for f in CONTENT_FIELDS) and not can(actor, Action.EDIT, facts):
        raise errors.Forbidden("You can't change this list.")
    if any(f in changes for f in SETTINGS_FIELDS) and not can(actor, Action.SETTINGS, facts):
        raise errors.Forbidden("Only the list's owner can change its settings.")
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
    return locked


@transaction.atomic
def delete_list(principal: Principal, list_id: UUID) -> None:
    locked, actor, facts = _lock(principal, list_id)
    if not can(actor, Action.DELETE, facts):
        raise errors.Forbidden("Only the list's owner can delete it.")
    locked.delete()  # cascades to links, redirects and memberships
    logger.info("Deleted list %s", list_id)


@transaction.atomic
def rotate_owner_token(principal: Principal, list_id: UUID) -> str:
    """Replace a legacy list's owner token; the old one stops working at once (V1 behaviour)."""
    locked, actor, facts = _lock(principal, list_id)
    if not can(actor, Action.ROTATE_TOKEN, facts):
        raise errors.Forbidden("Only the holder of this list's edit link can replace it.")
    owner_token = tokens.generate_owner_token()
    locked.owner_token_hash = tokens.hash_owner_token(owner_token)
    locked.save(update_fields=["owner_token_hash", "updated_at"])
    logger.info("Rotated owner token of list %s", locked.id)
    return owner_token


def _lock(
    principal: Principal, list_id: UUID, *, with_email: bool = False
) -> tuple[SharedList, Actor, ListFacts]:
    """Lock the list row and decide who the principal is on it *now*."""
    locked = SharedList.objects.select_for_update().filter(pk=list_id).first()
    if locked is None:
        raise errors.NotVisible()
    actor = actor_for(principal, locked, with_email=with_email)
    facts = facts_for(principal, locked)
    if not can(actor, Action.VIEW, facts):
        raise errors.NotVisible()
    if locked.is_expired:
        raise errors.Expired("This list has expired.")
    return locked, actor, facts
