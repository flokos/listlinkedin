"""Reading history (docs/v2/07-REVISION-SPEC.md). Callers check that the reader may see the
list's history (the policy's VIEW_HISTORY) before calling these."""

from django.db.models import QuerySet
from rest_framework.exceptions import NotFound

from .domain import snapshot
from .models import ListRevision


def revisions_of(shared_list) -> QuerySet[ListRevision]:
    """A list's revisions, newest first."""
    return (
        ListRevision.objects.filter(shared_list=shared_list)
        .select_related("created_by")
        .order_by("-number")
    )


def get_revision(shared_list, number: int) -> ListRevision:
    revision = revisions_of(shared_list).filter(number=number).first()
    if revision is None:
        raise NotFound("This list has no such revision.")
    return revision


def snapshot_of(revision: ListRevision) -> dict:
    """The revision's snapshot in the current schema (upcast if it is older)."""
    return snapshot.upcast(revision.snapshot)


def previous_snapshot(revision: ListRevision) -> dict | None:
    if revision.number == 1:
        return None
    stored = ListRevision.objects.values_list("snapshot", flat=True).get(
        shared_list_id=revision.shared_list_id, number=revision.number - 1
    )
    return snapshot.upcast(stored)
