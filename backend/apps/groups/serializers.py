from django.conf import settings
from rest_framework import serializers

from apps.metadata import images
from apps.sharing.domain import MAX_DESCRIPTION_LENGTH
from apps.sharing.models import VISIBILITY_CHOICES
from apps.sharing.policy import (
    Visibility,
    group_permissions,
    group_role_of,
    shown_in_group,
)
from apps.sharing.v2.serializers import (
    ListDetailSerializer,
    ListOwnerSerializer,
    MemberSerializer,
    tags_from,
    tags_input,
)

from .models import Group, GroupMembership
from .selectors import GroupAccess
from .services import VERIFY_EMAIL_TO_PUBLISH


class GroupDetailSerializer(serializers.ModelSerializer):
    """A group as the requesting user sees it. `list_count` counts only the lists the group
    shows them; `my_role` and `permissions` come from the policy."""

    url = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    owner = serializers.SerializerMethodField()
    list_count = serializers.IntegerField(help_text="The lists this group shows you.")
    my_role = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = [
            "id",
            "code",
            "slug",
            "url",
            "title",
            "description",
            "image_url",
            "visibility",
            "tags",
            "owner",
            "created_at",
            "updated_at",
            "list_count",
            "my_role",
            "permissions",
        ]
        read_only_fields = fields

    def _access(self, group: Group) -> GroupAccess:
        return self.context["access"][group.pk]

    def get_url(self, group: Group) -> str:
        return f"{settings.PUBLIC_BASE_URL}/g/{group.code}/{group.slug}"

    def get_image_url(self, group: Group) -> str | None:
        return images.url_for(group.image)

    def get_owner(self, group: Group) -> dict | None:
        """Shown on public groups and to members, as for lists. Never an email address."""
        access = self._access(group)
        if access.facts.visibility is not Visibility.PUBLIC and not group_role_of(
            access.actor, access.facts
        ):
            return None
        return ListOwnerSerializer({"display_name": group.owner.display_name}).data

    def get_my_role(self, group: Group) -> str | None:
        access = self._access(group)
        role = group_role_of(access.actor, access.facts)
        return role.value if role else None

    def get_permissions(self, group: Group) -> list[str]:
        access = self._access(group)
        return group_permissions(access.actor, access.facts)


class GroupWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(
        max_length=MAX_DESCRIPTION_LENGTH, allow_blank=True, required=False
    )
    visibility = serializers.ChoiceField(choices=VISIBILITY_CHOICES, required=False)
    tags = tags_input()

    def validate_visibility(self, value: str) -> Visibility:
        visibility = Visibility(value)
        if visibility is Visibility.PUBLIC and not self.context["email_verified"]:
            raise serializers.ValidationError(VERIFY_EMAIL_TO_PUBLISH)
        return visibility

    def validate_tags(self, value: list[str]) -> list[str]:
        return tags_from(value)


class GroupListSerializer(ListDetailSerializer):
    """A list in a group: the list's summary, as the viewer sees the list itself, plus
    whether everyone who can view the group is shown it."""

    shown_to_all = serializers.SerializerMethodField(
        help_text="False when you see this list only because of your own role on it: other "
        "people who can view the group don't (docs/v2/12-AUTHORIZATION.md)."
    )

    class Meta(ListDetailSerializer.Meta):
        fields = [*ListDetailSerializer.Meta.fields, "shown_to_all"]
        read_only_fields = fields

    def get_shown_to_all(self, shared_list) -> bool:
        return shown_in_group(
            has_list_role=False,
            list_visibility=Visibility(shared_list.visibility),
            group_visibility=Visibility(self.context["group"].visibility),
        )


class AddListSerializer(serializers.Serializer):
    list = serializers.CharField(max_length=32, help_text="The code of the list to add.")


class GroupReorderSerializer(serializers.Serializer):
    list = serializers.CharField(max_length=32, help_text="The code of the list to move.")
    to_index = serializers.IntegerField(
        min_value=0,
        help_text="Its new 0-based place among the lists you are shown (clamped to the end).",
    )


class GroupMemberSerializer(MemberSerializer):
    class Meta(MemberSerializer.Meta):
        model = GroupMembership
