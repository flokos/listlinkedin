import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class RevisionKind(models.TextChoices):
    CREATED = "created"
    EDITED = "edited"
    RESTORED = "restored"
    MIGRATED = "migrated"  # the baseline of a list that existed before V2
    FORKED = "forked"
    MERGED = "merged"  # reserved: synchronization is postponed (ADR-015)
    BRANCHED = "branched"  # reserved: synchronization is postponed (ADR-015)


class ListRevision(models.Model):
    """One immutable, numbered snapshot of a list's content (docs/v2/07-REVISION-SPEC.md).

    Rows are only ever inserted (apps.versioning.services) and deleted with their list. A
    database trigger rejects updates (migration 0002), and save() refuses them here too.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shared_list = models.ForeignKey(
        "sharing.SharedList", on_delete=models.CASCADE, related_name="revisions"
    )
    number = models.PositiveIntegerField()
    schema_version = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=16, choices=RevisionKind.choices)
    snapshot = models.JSONField()
    # Counts of what changed since the previous revision (apps.versioning.domain.diff).
    summary = models.JSONField(default=dict)
    restored_from = models.PositiveIntegerField(null=True, blank=True)
    # NULL for edit-link (legacy token) writes, migrations, and deleted accounts.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["shared_list", "number"], name="versioning_revision_number_unique"
            ),
            models.CheckConstraint(
                condition=Q(number__gte=1), name="versioning_revision_number_valid"
            ),
            models.CheckConstraint(
                condition=Q(kind__in=RevisionKind.values), name="versioning_revision_kind_valid"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.shared_list_id} r{self.number}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise TypeError("List revisions are immutable.")
        super().save(*args, **kwargs)
