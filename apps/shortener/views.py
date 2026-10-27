from django.http import HttpResponseRedirect
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.views import APIView

from .services import resolve_destination


class ShortRedirectView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        auth=[],
        responses={
            302: OpenApiResponse(description="Temporary redirect to the current destination."),
            404: OpenApiResponse(description="Unknown or deleted short code."),
            410: OpenApiResponse(description="The parent list expired or the code is inactive."),
        },
        summary="Resolve a short URL",
    )
    def get(self, request, code):
        # 302, never 301: the destination can change during the list's lifetime.
        response = HttpResponseRedirect(resolve_destination(code))
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response
