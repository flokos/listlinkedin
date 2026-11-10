from allauth.account.utils import has_verified_email
from rest_framework import serializers

from .models import User


class MeSerializer(serializers.ModelSerializer):
    """The signed-in user, as the user themself sees it. Only `display_name` is writable."""

    email_verified = serializers.SerializerMethodField()
    deletion_scheduled_for = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
        help_text="Set while the account is being deleted: when its data will be erased. "
        "Until then, POST /api/v2/me/restore/ undoes the deletion.",
    )

    class Meta:
        model = User
        fields = ["id", "email", "display_name", "email_verified", "deletion_scheduled_for"]
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


# Connected browsers (docs/v2/adr/ADR-020): the browser extension's sign-in.


class BrowserApprovalSerializer(serializers.Serializer):
    challenge = serializers.RegexField(
        r"^[A-Za-z0-9_-]{43}$",
        help_text="PKCE S256: base64url(SHA-256(verifier)) without padding, from the "
        "extension that asked to connect.",
    )
    name = serializers.CharField(
        max_length=80, help_text='What to call the browser, e.g. "Firefox on Linux".'
    )

    def validate_name(self, value: str) -> str:
        # A label shown back to the user and in the notice email: one line of plain text.
        name = " ".join("".join(ch for ch in value if ch.isprintable() or ch.isspace()).split())
        if not name:
            raise serializers.ValidationError("Give the browser a name.")
        return name


class BrowserApprovalResultSerializer(serializers.Serializer):
    code = serializers.CharField(help_text="One-time code for the extension. Shown once.")
    expires_in = serializers.IntegerField(help_text="Seconds until the code stops working.")


class BrowserConnectSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=128, help_text="The code from the approval.")
    verifier = serializers.RegexField(
        r"^[A-Za-z0-9._~-]{43,128}$",
        help_text="The PKCE verifier whose S256 challenge was approved (RFC 7636).",
    )


class ConnectedBrowserSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    connected_at = serializers.DateTimeField()
    last_used_at = serializers.DateTimeField(help_text="Updated at most once a day.")
    current = serializers.SerializerMethodField(
        help_text="True for the connection this request itself was made with."
    )

    def get_current(self, browser) -> bool:
        return browser.session_key == self.context.get("session_key")


class BrowserConnectionSerializer(serializers.Serializer):
    """What the extension gets once: its connection, the token, and whose account it is."""

    id = serializers.UUIDField()
    name = serializers.CharField()
    session_token = serializers.CharField(
        help_text="Send it as X-Session-Token on every request. It is never shown again."
    )
    user = MeSerializer()
