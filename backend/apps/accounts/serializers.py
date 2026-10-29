from allauth.account.utils import has_verified_email
from rest_framework import serializers

from .models import User


class MeSerializer(serializers.ModelSerializer):
    """The signed-in user, as the user themself sees it. Only `display_name` is writable."""

    email_verified = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "display_name", "email_verified"]
        read_only_fields = ["id", "email"]

    def validate_display_name(self, value: str) -> str:
        return value.strip()

    def get_email_verified(self, user: User) -> bool:
        return has_verified_email(user)


class DeleteAccountSerializer(serializers.Serializer):
    confirm = serializers.CharField(
        max_length=254, help_text="Your email address, typed to confirm the deletion."
    )


class SessionSerializer(serializers.Serializer):
    user = MeSerializer(allow_null=True, help_text="The signed-in user, or null when signed out.")
