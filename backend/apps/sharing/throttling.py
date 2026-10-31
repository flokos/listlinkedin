"""Rate limits shared by the list, group and account APIs (docs/v2/13-SECURITY.md#rate-limits)."""

from django.db import connection, transaction
from rest_framework.permissions import SAFE_METHODS
from rest_framework.throttling import ScopedRateThrottle


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
