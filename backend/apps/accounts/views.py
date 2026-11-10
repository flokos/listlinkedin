import uuid

from django.middleware.csrf import get_token
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.sharing.throttling import WriteRateThrottle

from . import browsers, selectors, services
from .authentication import API_AUTHENTICATION, SessionAuthentication
from .serializers import (
    BrowserApprovalResultSerializer,
    BrowserApprovalSerializer,
    BrowserConnectionSerializer,
    BrowserConnectSerializer,
    ConnectedBrowserSerializer,
    DeleteAccountSerializer,
    MeSerializer,
    SessionSerializer,
)

NOT_SIGNED_IN = OpenApiResponse(description="Not signed in.")


class SessionViewSet(viewsets.ViewSet):
    """Who is signed in. Also sets the CSRF cookie the SPA sends back as X-CSRFToken."""

    authentication_classes = API_AUTHENTICATION
    permission_classes = [AllowAny]
    allow_deleted_account = True  # shows a deleting account, so the app can offer to restore

    @extend_schema(responses={200: SessionSerializer}, summary="Current session")
    def retrieve(self, request):
        get_token(request)  # marks the csrftoken cookie to be set on this response
        user = request.user if request.user.is_authenticated else None
        return Response(SessionSerializer({"user": user}).data)


class MeViewSet(viewsets.ViewSet):
    """The signed-in user's own account."""

    authentication_classes = API_AUTHENTICATION
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
        # The cookie session, or the app client's token session (request.auth, ADR-019).
        (request.session if request.auth is None else request.auth).flush()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RestoreViewSet(viewsets.ViewSet):
    """Undo deleting your account, within the grace period (docs/v2/adr/ADR-016)."""

    authentication_classes = API_AUTHENTICATION
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


# Connected browsers (docs/v2/adr/ADR-020): how the browser extension signs in.

BROWSER_ID = OpenApiParameter("browser_id", uuid.UUID, OpenApiParameter.PATH)


class BrowserApprovalViewSet(viewsets.ViewSet):
    """Let a browser connect to your account. Only this site's own signed-in page can: the
    cookie session with its CSRF token, never a session token, so a connected browser (or
    another frontend) can't approve one."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [WriteRateThrottle]
    throttle_scope = "account"

    @extend_schema(
        request=BrowserApprovalSerializer,
        responses={
            201: BrowserApprovalResultSerializer,
            401: NOT_SIGNED_IN,
            409: OpenApiResponse(description="Ten browsers are connected (too_many_browsers)."),
        },
        summary="Approve connecting a browser",
    )
    def create(self, request):
        """Answers with a one-time code, valid for two minutes, that the page hands to the
        extension. It is worth nothing without the PKCE verifier behind `challenge`."""
        serializer = BrowserApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = browsers.approve_browser(request.user, **serializer.validated_data)
        expires_in = int(browsers.CODE_LIFETIME.total_seconds())
        result = BrowserApprovalResultSerializer({"code": code, "expires_in": expires_in})
        return Response(result.data, status=status.HTTP_201_CREATED)


class BrowserConnectViewSet(viewsets.ViewSet):
    """The extension's half: exchange an approval's code for a session token."""

    authentication_classes = []  # the code and its verifier are the credentials
    permission_classes = [AllowAny]
    throttle_classes = [WriteRateThrottle]
    throttle_scope = "browser_connect"

    @extend_schema(
        request=BrowserConnectSerializer,
        responses={
            201: BrowserConnectionSerializer,
            400: OpenApiResponse(
                description="The code is wrong, used, expired, or not this verifier's "
                "(invalid_code): one answer for all of them."
            ),
        },
        auth=[],
        summary="Connect a browser",
    )
    def create(self, request):
        """Works once per code. The session token signs in as the account that approved, on
        every `/api/v2/` endpoint, until the browser is disconnected, unused for 90 days or
        a year old, or the account's sessions end (password change, deletion, suspension)."""
        serializer = BrowserConnectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        browser, token = browsers.connect_browser(**serializer.validated_data)
        result = BrowserConnectionSerializer(
            {"id": browser.pk, "name": browser.name, "session_token": token, "user": browser.user}
        )
        return Response(result.data, status=status.HTTP_201_CREATED)


class ConnectedBrowserViewSet(viewsets.ViewSet):
    """The browsers connected to your account."""

    authentication_classes = API_AUTHENTICATION
    permission_classes = [IsAuthenticated]
    throttle_classes = [WriteRateThrottle]
    throttle_scope = "account"

    @extend_schema(
        responses={200: ConnectedBrowserSerializer(many=True), 401: NOT_SIGNED_IN},
        summary="Your connected browsers",
    )
    def list(self, request):
        """Newest first, at most ten, so not paginated. Only connections that still work."""
        # A connected browser asks with its own session token (request.auth, ADR-019).
        session_key = request.auth.session_key if request.auth is not None else None
        connected = selectors.connected_browsers(request.user)
        context = {"session_key": session_key}
        return Response(ConnectedBrowserSerializer(connected, many=True, context=context).data)

    @extend_schema(
        parameters=[BROWSER_ID],
        responses={
            204: None,
            401: NOT_SIGNED_IN,
            404: OpenApiResponse(description="No such connected browser on your account."),
        },
        summary="Disconnect a browser",
    )
    def destroy(self, request, browser_id=None):
        """Its token stops working at once. The extension disconnects itself this way too."""
        browsers.disconnect_browser(request.user, browser_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
