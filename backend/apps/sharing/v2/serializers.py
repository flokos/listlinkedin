from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.metadata import images

from ..domain import MAX_DESCRIPTION_LENGTH, MAX_TAGS, display_host, normalize_tags
from ..models import MEMBER_ROLE_CHOICES, VISIBILITY_CHOICES, ListMembership, SharedList
from ..policy import Visibility, permissions, role_of
from ..selectors import (
    DIRECTORY_ORDERINGS,
    MAX_QUERY_LENGTH,
    Access,
    current_metadata,
    metadata_status,
)
from ..serializers import LinkSerializer
from ..services.lists import VERIFY_EMAIL_TO_PUBLISH


class ListOwnerSerializer(serializers.Serializer):
    display_name = serializers.CharField()


class ListRefSerializer(serializers.Serializer):
    code = serializers.CharField()
    title = serializers.CharField()


# How a list came from another one. Only copies (forks) for now: synced copies are postponed.
ORIGIN_KIND_CHOICES = [("fork", "Fork")]


class OriginSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=ORIGIN_KIND_CHOICES)
    parent = ListRefSerializer(
        allow_null=True,
        help_text="The list this is a copy of; null if you can't view it (or it is gone).",
    )


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
    origin = serializers.SerializerMethodField()

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
            "tags",
            "owner",
            "legacy",
            "created_at",
            "updated_at",
            "expires_at",
            "head_revision",
            "link_count",
            "my_role",
            "permissions",
            "origin",
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

    @extend_schema_field(OriginSerializer(allow_null=True))
    def get_origin(self, shared_list: SharedList) -> dict | None:
        """Null for an ordinary list. For a copy, the list it was copied from, if the viewer
        may see it (`fork_sources` in the context: selectors.fork_sources)."""
        if shared_list.forked_from_id is None:
            return None
        parent = self.context["fork_sources"].get(shared_list.forked_from_id)
        return {"kind": "fork", "parent": parent}

    def _pair(self, shared_list: SharedList):
        access = self._access(shared_list)
        return access.actor, access.facts


def tags_input() -> serializers.ListField:
    """The `tags` field of list and group writes; `validate_tags` normalizes (tags_from)."""
    return serializers.ListField(
        child=serializers.CharField(max_length=64, allow_blank=True),
        max_length=MAX_TAGS * 2,  # duplicates and blanks are dropped before the real check
        required=False,
        help_text=f"At most {MAX_TAGS}: lowercase letters, digits and hyphens (normalized).",
    )


class ListWriteSerializer(serializers.Serializer):
    """Fields a client may set. Ownership, codes, timestamps and counts are never writable."""

    title = serializers.CharField(max_length=255)
    description = serializers.CharField(
        max_length=MAX_DESCRIPTION_LENGTH, allow_blank=True, required=False
    )
    visibility = serializers.ChoiceField(choices=VISIBILITY_CHOICES, required=False)
    allow_fork = serializers.BooleanField(required=False)
    allow_branch = serializers.BooleanField(required=False)
    tags = tags_input()
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

    def validate_tags(self, value: list[str]) -> list[str]:
        return tags_from(value)


def tags_from(value: list[str]) -> list[str]:
    try:
        return normalize_tags(value)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.messages) from None


class ForkSerializer(serializers.Serializer):
    title = serializers.CharField(
        max_length=255, required=False, help_text='Default: "{the list\'s title} (copy)".'
    )


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


class LinkFetchedSerializer(serializers.Serializer):
    title = serializers.CharField(allow_null=True)
    description = serializers.CharField(allow_null=True)
    icon_url = serializers.CharField(allow_null=True)
    site_name = serializers.CharField(allow_null=True)


METADATA_STATUSES = ["pending", "ready", "unavailable", "disabled"]


def link_display(link) -> dict:
    """What to show for a link: the user's own fields win, then fetched metadata, then a
    fallback (docs/v2/04-DOMAIN-MODEL.md, invariant 6). Computed here so clients don't
    re-implement the precedence. Fetched values count only when they describe the link's
    current URL (selectors.current_metadata)."""
    fetched = current_metadata(link) or {}
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
    fetched = serializers.SerializerMethodField(
        help_text="What the page itself says (null until fetched): offered as suggestions. "
        "Never copied into the link's own fields."
    )
    metadata_status = serializers.SerializerMethodField(
        help_text="pending (being fetched), ready, unavailable (couldn't be fetched) or "
        "disabled (fetching is off on this server)."
    )

    class Meta(LinkSerializer.Meta):
        fields = [
            *LinkSerializer.Meta.fields,
            "description",
            "icon_url",
            "display",
            "fetched",
            "metadata_status",
            "position",
            "source_link_id",
        ]
        read_only_fields = [*LinkSerializer.Meta.read_only_fields, "source_link_id"]

    def get_icon_url(self, link) -> str | None:
        return images.url_for(link.icon)

    @extend_schema_field(LinkDisplaySerializer)
    def get_display(self, link) -> dict:
        return link_display(link)

    @extend_schema_field(LinkFetchedSerializer(allow_null=True))
    def get_fetched(self, link) -> dict | None:
        fetched = current_metadata(link)
        if fetched is None:
            return None
        return {
            "title": fetched.get("title"),
            "description": fetched.get("description"),
            "icon_url": images.url_for(fetched.get("icon")),
            "site_name": fetched.get("site_name"),
        }

    @extend_schema_field(serializers.ChoiceField(choices=METADATA_STATUSES))
    def get_metadata_status(self, link) -> str:
        return metadata_status(link)

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


class DirectoryQuerySerializer(serializers.Serializer):
    """The directory's query parameters (docs/v2/09-API-DESIGN.md#directory)."""

    q = serializers.CharField(
        max_length=MAX_QUERY_LENGTH,
        required=False,
        allow_blank=True,
        help_text='Web-search syntax over titles and descriptions: words, "a phrase", -word, '
        "or. Partial words match titles.",
    )
    tags = serializers.CharField(
        required=False, allow_blank=True, help_text="Comma-separated; all must match."
    )
    ordering = serializers.ChoiceField(
        choices=DIRECTORY_ORDERINGS,
        required=False,
        help_text="Default: -relevance with q, else -updated_at.",
    )

    def validate_tags(self, value: str) -> list[str]:
        return tags_from(value.split(","))

    def validate(self, data):
        data["q"] = data.get("q", "").strip()
        data.setdefault("tags", [])
        data.setdefault("ordering", "-relevance" if data["q"] else "-updated_at")
        return data


class TagCountSerializer(serializers.Serializer):
    tag = serializers.CharField()
    count = serializers.IntegerField(help_text="Public lists and groups with this tag.")
