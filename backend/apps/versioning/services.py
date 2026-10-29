"""Writing revisions (docs/v2/07-REVISION-SPEC.md#mutation-rules).

`record_revision` is called by every content mutation, inside its transaction and while it
holds the list's row lock (wired in by task 3.2). It snapshots the live content, compares it
with the head revision, and writes revision head+1 only if the content changed, so a no-op
writes nothing. The lock serializes writers, so numbers have no gaps or duplicates; the unique
(list, number) constraint is the backstop, and a violation is a bug, never retried.
"""

from django.db import connection

from apps.sharing.models import SharedList
from apps.sharing.selectors import live_content

from .domain import diff, snapshot
from .models import ListRevision, RevisionKind


def record_revision(
    locked: SharedList,
    *,
    kind: RevisionKind,
    user=None,
    restored_from: int | None = None,
) -> ListRevision | None:
    """Write the next revision of `locked` if its content changed; return it, or None.
    A list's first revision is always written (there is nothing to compare it with).

    `locked` must be the list row locked with select_for_update in the current transaction.
    `user` is the acting account, or None for an edit link (legacy token).
    """
    if not connection.in_atomic_block:
        raise RuntimeError("record_revision must run inside the mutation's transaction.")
    current = snapshot.build(**live_content(locked))
    head = head_snapshot(locked)
    if head is not None and snapshot.same_content(head, current):
        return None
    revision = ListRevision.objects.create(
        shared_list=locked,
        number=locked.head_revision + 1,
        schema_version=snapshot.CURRENT_VERSION,
        kind=kind,
        snapshot=current,
        summary=diff.summarize(head, current),
        restored_from=restored_from,
        created_by=user,
    )
    locked.head_revision = revision.number
    # The one field of a list versioning writes: always together with the revision.
    SharedList.objects.filter(pk=locked.pk).update(head_revision=revision.number)
    return revision


def head_snapshot(shared_list: SharedList) -> dict | None:
    """The head revision's snapshot, upcast to the current schema; None before the first."""
    if not shared_list.head_revision:
        return None
    stored = ListRevision.objects.values_list("snapshot", flat=True).get(
        shared_list=shared_list, number=shared_list.head_revision
    )
    return snapshot.upcast(stored)
