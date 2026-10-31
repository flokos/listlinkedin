from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .domain import diff
from .models import ListRevision
from .selectors import previous_snapshot, snapshot_of

DELETED_ACCOUNT = "Deleted account"


class RevisionAuthorSerializer(serializers.Serializer):
    display_name = serializers.CharField()


@extend_schema_field(
    {
        "oneOf": [
            {"type": "object", "properties": {"display_name": {"type": "string"}}},
            {"type": "string", "enum": ["edit link"]},
        ],
        "nullable": True,
        "description": 'The account that made the change, "edit link" for a V1 edit link '
        "(revisions from before v2.1.0), "
        "or null for the baseline of a list that existed before V2.",
    }
)
class RevisionAuthorField(serializers.Field):
    def to_representation(self, revision: ListRevision):
        user = revision.created_by
        if user is None:
            return None if revision.kind == "migrated" else "edit link"
        if user.deleted_at is not None:  # being deleted or erased (docs/v2/adr/ADR-016)
            return {"display_name": DELETED_ACCOUNT}
        return {"display_name": user.display_name}


class RevisionSerializer(serializers.ModelSerializer):
    """A history entry: who changed what, when (docs/v2/09-API-DESIGN.md#revisions-and-restore)."""

    author = RevisionAuthorField(source="*")

    class Meta:
        model = ListRevision
        fields = ["number", "kind", "created_at", "author", "summary", "restored_from"]
        read_only_fields = fields


class RevisionDetailSerializer(RevisionSerializer):
    """One revision with its full content and every change since the one before it."""

    snapshot = serializers.SerializerMethodField()
    diff_from_previous = serializers.SerializerMethodField()

    class Meta(RevisionSerializer.Meta):
        fields = [*RevisionSerializer.Meta.fields, "snapshot", "diff_from_previous"]
        read_only_fields = fields

    def get_snapshot(self, revision: ListRevision) -> dict:
        return snapshot_of(revision)

    def get_diff_from_previous(self, revision: ListRevision) -> dict:
        return diff.compare(previous_snapshot(revision), snapshot_of(revision))


class RestoreSerializer(serializers.Serializer):
    revision = serializers.IntegerField(min_value=1, help_text="The revision to restore.")


class RestoreResultSerializer(serializers.Serializer):
    revision = serializers.IntegerField(help_text="The list's head revision after the restore.")
    changed = serializers.BooleanField(
        help_text="False if the list already had that content (no new revision)."
    )
