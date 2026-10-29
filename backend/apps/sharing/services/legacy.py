"""Write operations on legacy lists, authorized by their owner token: the V1 path.

`/api/v1/` uses these, and creating a list here makes a legacy list (no owner account,
unlisted, expiring in 30 days). Account-owned lists go through `services.lists`.

Every write re-reads the list with a row lock inside a transaction. That serializes
concurrent writes to the same list (link limit, duplicate checks, delete vs. update) and
re-checks expiration and the owner token at the moment of the write.
"""

import logging
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.shortener.services import create_redirect, create_with_unique_code

from .. import tokens
from ..domain import LIST_LIFETIME, MAX_LINKS_PER_LIST, slug_for
from ..exceptions import Gone
from ..models import PUBLIC_CODE_CONSTRAINT, SharedLink, SharedList
from ..policy import Visibility

logger = logging.getLogger(__name__)


def create_list(*, title: str) -> tuple[SharedList, str]:
    """Create a legacy list and return it with its plaintext owner token (never stored)."""
    owner_token = tokens.generate_owner_token()
    created_at = timezone.now()

    shared_list = create_with_unique_code(
        lambda code: SharedList.objects.create(
            public_code=code,
            owner_token_hash=tokens.hash_owner_token(owner_token),
            title=title,
            slug=slug_for(title),
            visibility=Visibility.UNLISTED.value,  # what V1 lists are: anyone with the URL
            created_at=created_at,
            expires_at=created_at + LIST_LIFETIME,
        ),
        PUBLIC_CODE_CONSTRAINT,
    )
    logger.info("Created list %s", shared_list.id)
    return shared_list, owner_token


@transaction.atomic
def update_list(shared_list: SharedList, *, title: str) -> SharedList:
    locked = _lock_active_list(shared_list)
    locked.title = title
    locked.slug = slug_for(title)
    locked.save(update_fields=["title", "slug", "updated_at"])
    return locked


@transaction.atomic
def rotate_owner_token(shared_list: SharedList) -> str:
    """Replace the owner token; the old one stops working immediately."""
    locked = _lock_active_list(shared_list)
    owner_token = tokens.generate_owner_token()
    locked.owner_token_hash = tokens.hash_owner_token(owner_token)
    locked.save(update_fields=["owner_token_hash", "updated_at"])
    logger.info("Rotated owner token of list %s", locked.id)
    return owner_token


@transaction.atomic
def delete_list(shared_list: SharedList) -> None:
    _lock_active_list(shared_list).delete()  # cascades to links and redirects
    logger.info("Deleted list %s", shared_list.id)


@transaction.atomic
def add_link(shared_list: SharedList, *, destination_url: str, title: str | None = None):
    locked = _lock_active_list(shared_list)
    if locked.links.count() >= MAX_LINKS_PER_LIST:
        raise ValidationError(f"A list can contain at most {MAX_LINKS_PER_LIST} links.")
    _ensure_not_duplicate(locked, destination_url)

    link = SharedLink.objects.create(
        shared_list=locked, destination_url=destination_url, title=title
    )
    create_redirect(link)
    return link


@transaction.atomic
def update_link(shared_list: SharedList, link_id: UUID, **changes) -> SharedLink:
    """Apply validated `title` / `destination_url` changes. The short code is never touched."""
    locked = _lock_active_list(shared_list)
    link = _get_link(locked, link_id)

    new_destination = changes.get("destination_url")
    if new_destination is not None and new_destination != link.destination_url:
        _ensure_not_duplicate(locked, new_destination)

    for field, value in changes.items():
        setattr(link, field, value)
    link.save(update_fields=[*changes, "updated_at"])
    return link


@transaction.atomic
def delete_link(shared_list: SharedList, link_id: UUID) -> None:
    locked = _lock_active_list(shared_list)
    _get_link(locked, link_id).delete()  # cascades to its redirects


def _lock_active_list(authorized: SharedList) -> SharedList:
    """Lock and re-read the list the caller was authorized against.

    The owner check ran on an unlocked read. If the token was rotated since then, the
    caller's token is no longer valid, so reject instead of acting on stale authorization.
    """
    locked = SharedList.objects.select_for_update().filter(pk=authorized.pk).first()
    if locked is None:
        raise NotFound()
    if locked.is_expired:
        raise Gone()
    if locked.owner_token_hash != authorized.owner_token_hash:
        raise PermissionDenied("The owner token was rotated during this request.")
    return locked


def _get_link(shared_list: SharedList, link_id: UUID) -> SharedLink:
    # Scoped to the list, so a link id from another list is simply "not found".
    link = shared_list.links.filter(pk=link_id).first()
    if link is None:
        raise NotFound()
    return link


def _ensure_not_duplicate(shared_list: SharedList, destination_url: str) -> None:
    if shared_list.links.filter(destination_url=destination_url).exists():
        raise ValidationError({"destination_url": ["This URL is already in the list."]})
