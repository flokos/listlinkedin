"""Restoring a list to an earlier revision (docs/v2/07-REVISION-SPEC.md#restoration).

The live rows are made equal to the snapshot, link by link, keyed by id: links in it are
revived (same id, short code and source) or updated and put in its order; live links not in
it are deleted (tombstoned). The list's title and description come back too. A new revision
records the restore (`restored`, `restored_from = N`); history is never rewritten (R5).
Settings and fetched metadata are not part of a snapshot and stay as they are.
"""

import logging
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.common import errors
from apps.versioning.domain import snapshot
from apps.versioning.models import RevisionKind
from apps.versioning.selectors import get_revision, snapshot_of
from apps.versioning.services import head_snapshot, record_revision

from ..domain import slug_for
from ..models import SharedLink
from ..policy import Action, can
from ..selectors import Principal
from .lists import _lock, check_head, denied

logger = logging.getLogger(__name__)


@transaction.atomic
def restore_revision(
    principal: Principal, list_id: UUID, number: int, *, expected_head: int | None
) -> tuple[int, bool]:
    """Returns (head revision, whether anything changed). `expected_head` is required: a
    restore is a decision made while looking at one state of the list."""
    if expected_head is None:
        raise errors.PreconditionRequired(
            'Restoring needs the list\'s current ETag in If-Match, e.g. If-Match: "r12".'
        )
    locked, actor, facts = _lock(principal, list_id)
    if not can(actor, Action.EDIT, facts):
        raise denied(principal, "You can't change this list.")
    check_head(locked, expected_head)
    target = snapshot_of(get_revision(locked, number))
    if snapshot.same_content(target, head_snapshot(locked)):
        return locked.head_revision, False  # already the content of revision N

    rows = {str(link.pk): link for link in SharedLink.objects.filter(shared_list=locked)}
    wanted = [link["id"] for link in target["links"]]
    missing = [link_id for link_id in wanted if link_id not in rows]
    if missing:  # rows are never deleted before their list: this is a bug, not a user error
        raise RuntimeError(f"Revision {number} of list {locked.pk} names unknown links {missing}")

    now = timezone.now()
    # 1. Delete the live links the revision doesn't have, so their URLs are free.
    gone = [
        row.pk for link_id, row in rows.items() if row.deleted_at is None and link_id not in wanted
    ]
    SharedLink.objects.filter(pk__in=gone).update(deleted_at=now, position=None, updated_at=now)
    # 2. Park the URLs that change, so swapping URLs between links can't collide with the
    #    unique (list, URL) index on live links, which is checked row by row.
    changing = [
        rows[link["id"]]
        for link in target["links"]
        if rows[link["id"]].destination_url != link["url"] and rows[link["id"]].deleted_at is None
    ]
    for row in changing:
        SharedLink.objects.filter(pk=row.pk).update(destination_url=f"restore:{row.pk}")
    # 3. Revive and update every link of the revision, in its order (positions are a deferred
    #    constraint, checked at commit).
    for position, link in enumerate(target["links"]):
        SharedLink.objects.filter(pk=rows[link["id"]].pk).update(
            destination_url=link["url"],
            title=link["title"],
            description=link["description"],
            icon=link["icon"],
            position=position,
            deleted_at=None,
            updated_at=now,
        )
    # 4. The list's own content.
    content = target["list"]
    if (locked.title, locked.description) != (content["title"], content["description"]):
        locked.title, locked.description = content["title"], content["description"]
        locked.slug = slug_for(locked.title)
        locked.save(update_fields=["title", "description", "slug", "updated_at"])

    revision = record_revision(
        locked, kind=RevisionKind.RESTORED, user=principal.user, restored_from=number
    )
    if revision is not None:
        logger.info("Restored list %s to revision %s as %s", locked.pk, number, revision.number)
    return locked.head_revision, revision is not None
