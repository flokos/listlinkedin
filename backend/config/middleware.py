import re

from django.conf import settings
from django.db import DatabaseError, connection
from django.http import JsonResponse

from .logging import REQUEST_ID, USER_ID, request_id_from


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


def request_id(get_response):
    """Give the request an id: nginx's X-Request-ID, or a new one. Every log record made while
    handling it carries the id (config.logging), and the response echoes it, so a problem
    someone reports can be found in the api's and nginx's logs."""

    def middleware(request):
        value = request_id_from(request.META.get("HTTP_X_REQUEST_ID"))
        token = REQUEST_ID.set(value)
        try:
            response = get_response(request)
        finally:
            REQUEST_ID.reset(token)
        response["X-Request-ID"] = value
        return response

    return middleware


def log_user(get_response):
    """Put the signed-in user's id on the request's log records (after authentication)."""

    def middleware(request):
        user = getattr(request, "user", None)
        signed_in = user is not None and user.is_authenticated
        token = USER_ID.set(str(user.pk) if signed_in else "-")
        try:
            return get_response(request)
        finally:
            USER_ID.reset(token)

    return middleware


# API answers are personal (lists you may see, your account) and change at any time: browsers
# and proxies must not store them (ASVS V14.3.2). The app's files keep their own caching.
NO_STORE = re.compile(r"^/(api|_allauth|r)/")


def no_store(get_response):
    def middleware(request):
        response = get_response(request)
        if NO_STORE.match(request.path) and not response.has_header("Cache-Control"):
            response["Cache-Control"] = "no-store"
        return response

    return middleware


# Django answers with JSON, redirects and the API docs page, never with pages that load
# anything (ASVS V3.4.3, V3.4.6). A view that needs more sets its own (config.docs).
API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


def content_security_policy(get_response):
    def middleware(request):
        response = get_response(request)
        if not response.has_header("Content-Security-Policy"):
            response["Content-Security-Policy"] = API_CSP
        return response

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
