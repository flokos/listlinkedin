from django.middleware.csrf import get_token
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.sharing.permissions import WriteRateThrottle

from . import services
from .authentication import SessionAuthentication
from .serializers import MeSerializer, SessionSerializer

NOT_SIGNED_IN = OpenApiResponse(description="Not signed in.")


class SessionViewSet(viewsets.ViewSet):
    """Who is signed in. Also sets the CSRF cookie the SPA sends back as X-CSRFToken."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]

    @extend_schema(responses={200: SessionSerializer}, summary="Current session")
    def retrieve(self, request):
        get_token(request)  # marks the csrftoken cookie to be set on this response
        user = request.user if request.user.is_authenticated else None
        return Response(SessionSerializer({"user": user}).data)


class MeViewSet(viewsets.ViewSet):
    """The signed-in user's own account."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [WriteRateThrottle]
    throttle_scope = "account"

    @extend_schema(responses={200: MeSerializer, 401: NOT_SIGNED_IN}, summary="Your account")
    def retrieve(self, request):
        return Response(MeSerializer(request.user).data)

    @extend_schema(
        request=MeSerializer,
        responses={200: MeSerializer, 401: NOT_SIGNED_IN},
        summary="Update your display name",
    )
    def partial_update(self, request):
        serializer = MeSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        display_name = serializer.validated_data.get("display_name", request.user.display_name)
        user = services.update_profile(request.user, display_name=display_name)
        return Response(MeSerializer(user).data)
