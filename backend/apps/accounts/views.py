from django.middleware.csrf import get_token
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.sharing.throttling import WriteRateThrottle

from . import services
from .authentication import SessionAuthentication
from .serializers import DeleteAccountSerializer, MeSerializer, SessionSerializer

NOT_SIGNED_IN = OpenApiResponse(description="Not signed in.")


class SessionViewSet(viewsets.ViewSet):
    """Who is signed in. Also sets the CSRF cookie the SPA sends back as X-CSRFToken."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]
    allow_deleted_account = True  # shows a deleting account, so the app can offer to restore

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

    @extend_schema(
        request=DeleteAccountSerializer,
        responses={
            204: None,
            400: OpenApiResponse(description="The email doesn't match."),
            401: NOT_SIGNED_IN,
        },
        summary="Delete your account and the lists you own",
    )
    def destroy(self, request):
        """Deletes the account: at once, every session ends, the lists you own are hidden and
        you disappear from lists you were added to. Everything is erased after 30 days; until
        then, signing in offers to restore it. Type your email address in `confirm`."""
        serializer = DeleteAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.delete_account(request.user, confirm=serializer.validated_data["confirm"])
        request.session.flush()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RestoreViewSet(viewsets.ViewSet):
    """Undo deleting your account, within the grace period (docs/v2/adr/ADR-016)."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [WriteRateThrottle]
    throttle_scope = "account"
    allow_deleted_account = True

    @extend_schema(
        request=None,
        responses={
            200: MeSerializer,
            401: NOT_SIGNED_IN,
            409: OpenApiResponse(description="The account was already erased."),
        },
        summary="Restore your account",
    )
    def create(self, request):
        """Restores the account and everything it had: lists, memberships, name. Answers with
        the account (`deletion_scheduled_for` is null again)."""
        return Response(MeSerializer(services.restore_account(request.user)).data)
