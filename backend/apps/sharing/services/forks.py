"""Forks: "Make a copy" (docs/v2/08-SYNCHRONIZATION-SPEC.md#fork-vs-branch).

A fork is an ordinary, independent list owned by the person who made it. It records where it
came from (`forked_from_id`, and `source_link_id` on each link) for attribution only: it never
receives the source's changes. (Synced copies, branches, are postponed: ADR-015.)

The copy is made from the source's head revision. That snapshot is immutable, so the source
isn't locked and its writers never wait for a copy; a change that lands meanwhile simply isn't
in it, as if the copy had been made a moment earlier. Everything the copy creates (the list,
its links, their short URLs and revision 1 `forked`) is one transaction.
"""

import logging
from uuid import UUID

from django.db import IntegrityError, transaction

from apps.common import errors
from apps.shortener.services import create_redirect, create_with_unique_code
from apps.versioning.models import RevisionKind
from apps.versioning.services import head_snapshot, record_revision

from ..domain import slug_for
from ..models import CREATION_KEY_CONSTRAINT, PUBLIC_CODE_CONSTRAINT, SharedLink, SharedList
from ..policy import Action, Visibility, can
from ..selectors import Principal, get_list_for
from .lists import _created_with, _relock, _violated_constraint, denied

logger = logging.getLogger(__name__)

TITLE_MAX_LENGTH = SharedList._meta.get_field("title").max_length
CANNOT_FORK = "The owner of this list doesn't allow copies."


def copy_title(title: str) -> str:
    """The default title of a copy: "{title} (copy)", shortened to fit."""
    suffix = " (copy)"
    return title[: TITLE_MAX_LENGTH - len(suffix)] + suffix


@transaction.atomic
def fork_list(
    principal: Principal,
    code: str,
    *,
    title: str | None = None,
    creation_key: UUID | None = None,
) -> tuple[SharedList, bool]:
    """Copy the list with this code into a new list the signed-in user owns. Returns
    (copy, created); retrying with the same `creation_key` returns the first copy.

    Allowed to the source's owner, and to anyone signed in who can view it when its owner
    allows copies (`allow_fork`). The copy is private, permanent and doesn't allow copies;
    its title, description, image and links are the source's, the links with new ids and
    short URLs. Fetched metadata is copied too, but only for a link whose URL is unchanged.
    """
    if principal.user is None:
        raise errors.AuthenticationRequired("Sign in to make a copy of this list.")
    source, access = get_list_for(principal, code)  # 404 if not viewable, 410 if expired
    if not can(access.actor, Action.FORK, access.facts):
        raise denied(principal, CANNOT_FORK)
    if creation_key is not None and (existing := _forked_with(creation_key, principal, source)):
        return existing, False

    content = head_snapshot(source)
    if content is None:  # every list has revision 1 from its creation or the V2 baseline
        raise RuntimeError(f"List {source.pk} has no revision to copy.")
    name = title or copy_title(content["list"]["title"])
    try:
        fork = create_with_unique_code(
            lambda code: SharedList.objects.create(
                public_code=code,
                owner=principal.user,
                title=name,
                slug=slug_for(name),
                description=content["list"]["description"],
                image=source.image,
                visibility=Visibility.PRIVATE.value,
                forked_from_id=source.pk,
                creation_key=creation_key,
            ),
            PUBLIC_CODE_CONSTRAINT,
        )
    except IntegrityError as exc:
        # The same key, concurrently: the other request won. Answer with its copy.
        if _violated_constraint(exc) != CREATION_KEY_CONSTRAINT:
            raise
        return _forked_with(creation_key, principal, source), False

    _copy_links(source, fork, content["links"])
    fork = _relock(fork)
    record_revision(fork, kind=RevisionKind.FORKED, user=principal.user)
    logger.info("Forked list %s into %s", source.pk, fork.pk)
    return fork, True


def _copy_links(source: SharedList, fork: SharedList, links: list[dict]) -> None:
    # Metadata isn't in snapshots (it isn't content); take it from the live rows, and only
    # where it still describes the snapshot's URL.
    fetched = {
        str(link.pk): link
        for link in SharedLink.objects.filter(
            shared_list=source, pk__in=[link["id"] for link in links]
        ).only("pk", "destination_url", "metadata", "metadata_fetched_at")
    }
    copies = []
    for link in links:
        original = fetched.get(link["id"])
        same_url = original is not None and original.destination_url == link["url"]
        copies.append(
            SharedLink(
                shared_list=fork,
                destination_url=link["url"],
                title=link["title"],
                description=link["description"],
                icon=link["icon"],  # media files are shared; cleanup_media counts references
                position=link["position"],
                source_link_id=link["id"],
                metadata=original.metadata if same_url else {},
                metadata_fetched_at=original.metadata_fetched_at if same_url else None,
            )
        )
    for copy in SharedLink.objects.bulk_create(copies):
        create_redirect(copy)


def _forked_with(creation_key: UUID, principal: Principal, source: SharedList):
    """The list an earlier request with this key created, if it was a copy of `source`."""
    existing = _created_with(creation_key, principal.user)  # 409 if another user's key
    if existing is not None and existing.forked_from_id != source.pk:
        raise errors.Conflict(
            "This Idempotency-Key was already used.", code="idempotency_key_reused"
        )
    return existing
