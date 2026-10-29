from django.contrib.auth.models import AnonymousUser
from drf_spectacular.extensions import OpenApiAuthenticationExtension

from ..permissions import OwnerTokenAuthentication
from ..selectors import Principal


class LegacyTokenAuthentication(OwnerTokenAuthentication):
    """A V1 owner token (`Authorization: Bearer`) on /api/v2/, together with the session user.

    Keeping the session user lets a signed-in user present a token (to claim a legacy list).
    A request with an Authorization header can't be forged cross-site (it would need a CORS
    preflight, which this API never grants), so these requests need no CSRF token. Requests
    without the header fall through to SessionAuthentication, which enforces CSRF.
    """

    def authenticate(self, request):
        result = super().authenticate(request)  # (None, token) or None
        if result is None:
            return None
        user = getattr(request._request, "user", None)  # Django's session user
        if user is None or not user.is_authenticated:
            user = AnonymousUser()
        return user, result[1]


class LegacyTokenScheme(OpenApiAuthenticationExtension):
    target_class = LegacyTokenAuthentication
    name = "LegacyOwnerToken"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "description": "A legacy (V1) list's owner token, until the list is claimed.",
        }


def principal_of(request) -> Principal:
    user = request.user if request.user and request.user.is_authenticated else None
    token = request.auth if isinstance(request.auth, str) else None
    return Principal(user=user, token=token)
