"""Authentication backends that refuse suspended accounts (docs/v2/13-SECURITY.md#moderation).

Django asks a backend `user_can_authenticate` both when someone signs in and when a session
is loaded on each request, so a suspended account can't sign in and its open sessions stop
working at once. The operator suspends and unsuspends accounts with management commands.
"""

from allauth.account import auth_backends
from django.contrib.auth import backends


def _not_suspended(user) -> bool:
    return getattr(user, "suspended_at", None) is None


class ModelBackend(backends.ModelBackend):
    def user_can_authenticate(self, user) -> bool:
        return super().user_can_authenticate(user) and _not_suspended(user)


class AuthenticationBackend(auth_backends.AuthenticationBackend):
    """allauth's backend (sign-in by email), with the same rule."""

    def user_can_authenticate(self, user) -> bool:
        return super().user_can_authenticate(user) and _not_suspended(user)
