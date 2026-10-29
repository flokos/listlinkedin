from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from ..domain import MAX_DESCRIPTION_LENGTH
from ..models import SharedList
from ..policy import Visibility, permissions, role_of
from ..selectors import Access
from ..services.lists import VERIFY_EMAIL_TO_PUBLISH

VISIBILITIES = [v.value for v in Visibility]


class ListOwnerSerializer(serializers.Serializer):
    display_name = serializers.CharField()


class ListDetailSerializer(serializers.ModelSerializer):
    """A list as the requesting user sees it. `my_role` and `permissions` come from the
    policy (docs/v2/12-AUTHORIZATION.md), so clients never re-derive the rules."""

    code = serializers.CharField(source="public_code")
    url = serializers.SerializerMethodField()
    owner = serializers.SerializerMethodField()
    legacy = serializers.BooleanField(source="is_legacy")
    link_count = serializers.IntegerField()
    my_role = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = SharedList
        fields = [
            "id",
            "code",
            "slug",
            "url",
            "title",
            "description",
            "visibility",
            "allow_fork",
            "allow_branch",
            "owner",
            "legacy",
            "created_at",
            "updated_at",
            "expires_at",
            "link_count",
            "my_role",
            "permissions",
        ]
        read_only_fields = fields

    def _access(self, shared_list: SharedList) -> Access:
        return self.context["access"][shared_list.pk]

    def get_url(self, shared_list: SharedList) -> str:
        return f"{settings.PUBLIC_BASE_URL}/l/{shared_list.public_code}/{shared_list.slug}"

    def get_owner(self, shared_list: SharedList) -> dict | None:
        """Shown on public lists and to members; email addresses are never shown."""
        access = self._access(shared_list)
        if shared_list.owner is None:
            return None
        visible = access.facts.visibility is Visibility.PUBLIC or role_of(
            access.actor, access.facts
        )
        if not visible:
            return None
        return ListOwnerSerializer({"display_name": shared_list.owner.display_name}).data

    def get_my_role(self, shared_list: SharedList) -> str | None:
        role = role_of(*self._pair(shared_list))
        return role.value if role else None

    def get_permissions(self, shared_list: SharedList) -> list[str]:
        return permissions(*self._pair(shared_list))

    def _pair(self, shared_list: SharedList):
        access = self._access(shared_list)
        return access.actor, access.facts


class ListWriteSerializer(serializers.Serializer):
    """Fields a client may set. Ownership, codes, timestamps and counts are never writable."""

    title = serializers.CharField(max_length=255)
    description = serializers.CharField(
        max_length=MAX_DESCRIPTION_LENGTH, allow_blank=True, required=False
    )
    visibility = serializers.ChoiceField(choices=VISIBILITIES, required=False)
    allow_fork = serializers.BooleanField(required=False)
    allow_branch = serializers.BooleanField(required=False)
    expires_at = serializers.DateTimeField(
        allow_null=True, required=False, help_text="Null makes the list permanent."
    )

    def validate_visibility(self, value: str) -> Visibility:
        visibility = Visibility(value)
        if visibility is Visibility.PUBLIC and not self.context["email_verified"]:
            raise serializers.ValidationError(VERIFY_EMAIL_TO_PUBLISH)
        return visibility

    def validate_expires_at(self, value):
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError("Choose a time in the future.")
        return value
