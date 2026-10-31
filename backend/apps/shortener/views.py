from django.http import HttpResponseRedirect
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.views import APIView

from apps.accounts.authentication import SessionAuthentication
from apps.sharing.selectors import Principal

from .services import resolve_destination


class ShortRedirectView(APIView):
    # The session lets members follow links in private lists. A GET needs no CSRF token,
    # and anonymous visitors simply have no user.
    authentication_classes = [SessionAuthentication]
    permission_classes = []

    @extend_schema(
        auth=[],
        responses={
            302: OpenApiResponse(description="Temporary redirect to the current destination."),
            404: OpenApiResponse(description="Unknown or deleted short code, or not visible."),
            410: OpenApiResponse(description="The parent list expired or the code is inactive."),
        },
        summary="Resolve a short URL",
    )
    def get(self, request, code):
        user = request.user if request.user.is_authenticated else None
        # 302, never 301: the destination can change during the list's lifetime.
        response = HttpResponseRedirect(resolve_destination(code, Principal(user=user)))
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response
