from django.conf import settings
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.metadata import images

from ..domain import MAX_DESCRIPTION_LENGTH, display_host
from ..models import MEMBER_ROLE_CHOICES, VISIBILITY_CHOICES, ListMembership, SharedList
from ..policy import Visibility, permissions, role_of
from ..selectors import Access
from ..serializers import LinkSerializer
from ..services.lists import VERIFY_EMAIL_TO_PUBLISH


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
    head_revision = serializers.IntegerField(
        help_text='The latest revision\'s number; also the ETag, as "r{head_revision}".'
    )
    image_url = serializers.SerializerMethodField()
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
            "image_url",
            "visibility",
            "allow_fork",
            "allow_branch",
            "owner",
            "legacy",
            "created_at",
            "updated_at",
            "expires_at",
            "head_revision",
            "link_count",
            "my_role",
            "permissions",
        ]
        read_only_fields = fields

    def _access(self, shared_list: SharedList) -> Access:
        return self.context["access"][shared_list.pk]

    def get_url(self, shared_list: SharedList) -> str:
        return f"{settings.PUBLIC_BASE_URL}/l/{shared_list.public_code}/{shared_list.slug}"

    def get_image_url(self, shared_list: SharedList) -> str | None:
        return images.url_for(shared_list.image)

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
    visibility = serializers.ChoiceField(choices=VISIBILITY_CHOICES, required=False)
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


def email_hint(email: str) -> str:
    """Enough of an address to tell people apart, without showing it: `b…@example.com`.
    Full addresses are shown only to their own account (docs/v2/12-AUTHORIZATION.md)."""
    local, _, domain = email.partition("@")
    return f"{local[:1]}…@{domain}"


class MemberSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="user.pk")
    display_name = serializers.CharField(source="user.display_name")
    email_hint = serializers.SerializerMethodField()
    is_you = serializers.SerializerMethodField()
    added_at = serializers.DateTimeField(source="created_at")

    class Meta:
        model = ListMembership
        fields = ["user_id", "display_name", "email_hint", "role", "added_at", "is_you"]
        read_only_fields = fields

    def get_email_hint(self, membership: ListMembership) -> str:
        return email_hint(membership.user.email)

    def get_is_you(self, membership: ListMembership) -> bool:
        return membership.user_id == self.context["user_id"]


class MemberAddSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    role = serializers.ChoiceField(choices=MEMBER_ROLE_CHOICES)


class MemberRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=MEMBER_ROLE_CHOICES)


class LinkDisplaySerializer(serializers.Serializer):
    title = serializers.CharField()
    description = serializers.CharField(allow_null=True)
    icon_url = serializers.CharField(allow_null=True)
    site_name = serializers.CharField()


def link_display(link) -> dict:
    """What to show for a link: the user's own fields win, then fetched metadata, then a
    fallback (docs/v2/04-DOMAIN-MODEL.md, invariant 6). Computed here so clients don't
    re-implement the precedence. Metadata keys: `title`, `description`, `icon` (a media path)
    and `site_name`, filled by the metadata worker from task 7.3."""
    fetched = link.metadata or {}
    host = display_host(link.destination_url)
    return {
        "title": link.title or fetched.get("title") or host,
        "description": link.description or fetched.get("description") or None,
        "icon_url": images.url_for(link.icon or fetched.get("icon")),
        "site_name": fetched.get("site_name") or host,
    }


class LinkDetailSerializer(LinkSerializer):
    """A link on /api/v2/: V1's fields plus `description`, the uploaded icon's `icon_url`,
    `display` (what to show, with the precedence applied), its `position` among the live
    links (0-based) and `source_link_id` (the link it was copied from, if any)."""

    description = serializers.CharField(
        max_length=MAX_DESCRIPTION_LENGTH, allow_null=True, allow_blank=True, required=False
    )
    position = serializers.IntegerField(
        min_value=0,
        required=False,
        help_text="0-based. On create: where to insert (clamped; default: at the end). "
        "Can't be changed here afterwards.",
    )

    icon_url = serializers.SerializerMethodField(
        help_text="The uploaded icon (128×128 WebP), set with PUT …/icon/."
    )

    display = serializers.SerializerMethodField()

    class Meta(LinkSerializer.Meta):
        fields = [
            *LinkSerializer.Meta.fields,
            "description",
            "icon_url",
            "display",
            "position",
            "source_link_id",
        ]
        read_only_fields = [*LinkSerializer.Meta.read_only_fields, "source_link_id"]

    def get_icon_url(self, link) -> str | None:
        return images.url_for(link.icon)

    @extend_schema_field(LinkDisplaySerializer)
    def get_display(self, link) -> dict:
        return link_display(link)

    def validate_description(self, value: str | None) -> str | None:
        return (value or "").strip() or None  # one representation of "no description"

    def validate_position(self, value: int) -> int:
        if self.instance is None and self.partial:  # PATCH
            raise serializers.ValidationError("Links are moved with the reorder endpoint.")
        return value


class ReorderSerializer(serializers.Serializer):
    link = serializers.UUIDField(help_text="The link to move.")
    to_index = serializers.IntegerField(
        min_value=0, help_text="Its new 0-based place among the live links (clamped to the end)."
    )


class MoveToListSerializer(serializers.Serializer):
    list = serializers.CharField(max_length=32, help_text="The target list's code.")


@extend_schema_field(OpenApiTypes.BINARY)  # a file part; drf-spectacular would say "uri"
class UploadedFileField(serializers.FileField):
    pass


class ImageUploadSerializer(serializers.Serializer):
    file = UploadedFileField(
        help_text="PNG, JPEG, WebP or GIF, at most 2 MB. Re-encoded to WebP and shrunk to fit "
        "(128×128 for link icons, 512×512 for list images)."
    )
