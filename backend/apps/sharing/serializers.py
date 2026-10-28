from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.urls import reverse
from rest_framework import serializers

from .domain import normalize_destination_url
from .models import SharedLink, SharedList


def _absolute_url(path: str) -> str:
    return f"{settings.PUBLIC_BASE_URL}{path}"


class ListSerializer(serializers.ModelSerializer):
    """Public list representation. Only `title` is writable (no mass assignment)."""

    public_url = serializers.SerializerMethodField()

    class Meta:
        model = SharedList
        fields = ["id", "public_code", "public_url", "title", "created_at", "expires_at"]
        read_only_fields = ["id", "public_code", "created_at", "expires_at"]

    def get_public_url(self, shared_list: SharedList) -> str:
        return _absolute_url(reverse("list-short-url", args=[shared_list.public_code]))


class ListCreatedSerializer(ListSerializer):
    """Creation response: the only representation that ever includes the owner token."""

    owner_token = serializers.CharField(
        read_only=True, help_text="Private. Shown once; store it to manage the list."
    )

    class Meta(ListSerializer.Meta):
        fields = [*ListSerializer.Meta.fields, "owner_token"]


class OwnerTokenSerializer(serializers.Serializer):
    owner_token = serializers.CharField(
        read_only=True, help_text="Private. The new owner token; the previous one is revoked."
    )


class LinkSerializer(serializers.ModelSerializer):
    short_url = serializers.SerializerMethodField()

    class Meta:
        model = SharedLink
        fields = ["id", "title", "destination_url", "short_url", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {"title": {"allow_null": True, "allow_blank": True}}

    def validate_title(self, value: str | None) -> str | None:
        return value or None  # one representation of "no title"

    def validate_destination_url(self, value: str) -> str:
        try:
            return normalize_destination_url(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def get_short_url(self, link: SharedLink) -> str | None:
        if link.short_code is None:
            return None
        return _absolute_url(reverse("short-redirect", args=[link.short_code]))
