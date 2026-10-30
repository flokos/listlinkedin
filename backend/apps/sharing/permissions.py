"""Owner-token access control.

There are no user accounts. A request "authenticates" only by presenting a bearer token;
whether that token owns the list is decided per list by `IsListOwnerOrReadOnly`.
"""

from django.db import connection, transaction
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.throttling import ScopedRateThrottle

from .tokens import verify_owner_token


class OwnerTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        # A missing or malformed header simply means "no token": public reads keep working,
        # and owner-only writes still answer 401.
        if len(parts) != 2 or parts[0].lower() != b"bearer":
            return None
        return None, parts[1].decode("latin-1")  # (no user, raw token as request.auth)

    def authenticate_header(self, request) -> str:
        return "Bearer"  # turns a missing token into 401 instead of 403


class IsListOwnerOrReadOnly(BasePermission):
    """Anyone may read; writes need the owner token of *this* list."""

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in SAFE_METHODS:
            return True
        return request.auth is not None and verify_owner_token(request.auth, obj.owner_token_hash)


class WriteRateThrottle(ScopedRateThrottle):
    """Scoped rate limit applied to unsafe methods only; public reads are not throttled.

    DRF reads the request history, modifies it and writes it back, so concurrent requests
    would all see the same stale history and slip past the limit. A transaction-scoped
    Postgres advisory lock per (scope, client) serializes that read-modify-write.
    """

    def allow_request(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return True
        lock_key = f"throttle:{getattr(view, self.scope_attr, '')}:{self.get_ident(request)}"
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", [lock_key])
            return super().allow_request(request, view)


class ReadRateThrottle(WriteRateThrottle):
    """Scoped rate limit on every method, per client IP even when signed in: for public reads
    that cost a search (the directory, docs/v2/13-SECURITY.md#rate-limits)."""

    def allow_request(self, request, view) -> bool:
        lock_key = f"throttle:{getattr(view, self.scope_attr, '')}:{self.get_ident(request)}"
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", [lock_key])
            return super(WriteRateThrottle, self).allow_request(request, view)

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class OwnerTokenScheme(OpenApiAuthenticationExtension):
    target_class = OwnerTokenAuthentication
    name = "OwnerToken"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "description": "Private owner token returned once when the list is created.",
        }
