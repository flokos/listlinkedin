import re

from django.conf import settings
from django.db import DatabaseError, connection
from django.http import JsonResponse


def health_check(get_response):
    """Answer `/healthz` before host validation and the HTTPS redirect.

    The container probe calls it over plain HTTP as 127.0.0.1, which SecurityMiddleware
    would redirect and ALLOWED_HOSTS would reject. The response depends on nothing but the
    database being reachable, so serving it to any host is harmless.
    """

    def middleware(request):
        if request.path != "/healthz":
            return get_response(request)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except DatabaseError:
            return JsonResponse({"status": "unavailable"}, status=503)
        return JsonResponse({"status": "ok"})

    return middleware


# The image upload endpoints (docs/v2/09-API-DESIGN.md#uploads): the only larger bodies.
UPLOAD_PATH = re.compile(
    r"^/api/v2/(?:lists/[^/]+/(?:image|links/[^/]+/icon)|groups/[^/]+/image)/$"
)


def request_size_limit(get_response):
    """Reject oversized bodies up front (DRF parsers bypass DATA_UPLOAD_MAX_MEMORY_SIZE)."""

    def middleware(request):
        try:
            length = int(request.META.get("CONTENT_LENGTH") or 0)
        except ValueError:
            length = 0
        if UPLOAD_PATH.match(request.path):
            limit = settings.UPLOAD_REQUEST_MAX_SIZE
        else:
            limit = settings.DATA_UPLOAD_MAX_MEMORY_SIZE
        if length > limit:
            return JsonResponse({"detail": "Request body too large."}, status=413)
        return get_response(request)

    return middleware


def noindex(get_response):
    """Ask crawlers not to index anything: list and short URLs are private capabilities."""

    def middleware(request):
        response = get_response(request)
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response

    return middleware
