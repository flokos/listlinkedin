from allauth.headless.contrib.rest_framework.authentication import XSessionTokenAuthentication
from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import authentication

from . import browsers


def _unless_deleted(request, result):
    """An account being deleted counts as signed out, except on the few views that say
    otherwise (`allow_deleted_account`): the session check and restoring it (ADR-016)."""
    if result is None or result[0].deleted_at is None:
        return result
    view = (getattr(request, "parser_context", None) or {}).get("view")
    return result if getattr(view, "allow_deleted_account", False) else None


class SessionAuthentication(authentication.SessionAuthentication):
    """Django session login with CSRF checks, as used by the SPA (docs/v2/09-API-DESIGN.md).

    DRF answers unauthenticated requests with 403 unless the first authenticator names a
    challenge. Naming one gives the 401 "sign in required" vs 403 "not allowed" split the
    API promises. "Session" is not a scheme browsers act on, so no login prompt appears.
    """

    def authenticate(self, request):
        return _unless_deleted(request, super().authenticate(request))

    def authenticate_header(self, request) -> str:
        return "Session"


class SessionTokenAuthentication(XSessionTokenAuthentication):
    """The session token of allauth's `app` client, in X-Session-Token: how frontends on
    other domains sign in (ADR-019). The token is the key of an ordinary Django session, so
    signing out, revoking sessions, suspension and erasure end it like a cookie session. No
    CSRF check: browsers never add the header by themselves.

    A connected browser's token (the browser extension, ADR-020) is such a token too, from a
    session that lasts longer; using it keeps that session alive (`browsers.touch_browser`)."""

    def authenticate(self, request):
        result = _unless_deleted(request, super().authenticate(request))
        if result is not None:
            browsers.touch_browser(result[1])
        return result


# Every API view accepts both. The session comes first: its challenge gives the 401s.
API_AUTHENTICATION = [SessionAuthentication, SessionTokenAuthentication]


class SessionScheme(OpenApiAuthenticationExtension):
    target_class = SessionAuthentication
    name = "SessionCookie"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": settings.SESSION_COOKIE_NAME,
            "description": (
                "Django session set by signing in through /_allauth/browser/v1/. Unsafe "
                "methods also need the X-CSRFToken header (from the csrftoken cookie)."
            ),
        }


class SessionTokenScheme(OpenApiAuthenticationExtension):
    target_class = SessionTokenAuthentication
    name = "SessionToken"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "X-Session-Token",
            "description": (
                "The session_token returned by signing in through /_allauth/app/v1/, for "
                "frontends on other domains (CORS_ALLOWED_ORIGINS), or by connecting a "
                "browser (POST /api/v2/browsers/connect/). No CSRF token needed."
            ),
        }
