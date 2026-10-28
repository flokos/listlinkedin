from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import authentication


class SessionAuthentication(authentication.SessionAuthentication):
    """Django session login with CSRF checks, as used by the SPA (docs/v2/09-API-DESIGN.md).

    DRF answers unauthenticated requests with 403 unless the first authenticator names a
    challenge. Naming one gives the 401 "sign in required" vs 403 "not allowed" split the
    API promises. "Session" is not a scheme browsers act on, so no login prompt appears.
    """

    def authenticate_header(self, request) -> str:
        return "Session"


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
