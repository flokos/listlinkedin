"""/api/v2/lists/: lists with accounts and visibility (docs/v2/09-API-DESIGN.md#lists).

Views do HTTP only. Who may do what is decided by the policy, through selectors (reads) and
services (writes, re-checked under the row lock).
"""

import re
import uuid

from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from apps.accounts.authentication import SessionAuthentication
from apps.common import errors
from apps.metadata.images import MAX_UPLOAD_BYTES
from apps.versioning import selectors as version_selectors
from apps.versioning.serializers import (
    RestoreResultSerializer,
    RestoreSerializer,
    RevisionDetailSerializer,
    RevisionSerializer,
)

from .. import selectors
from ..permissions import ReadRateThrottle, WriteRateThrottle
from ..policy import Action, Role, can
from ..serializers import OwnerTokenSerializer
from ..services import forks as fork_services
from ..services import links as link_services
from ..services import lists as services
from ..services import media as media_services
from ..services import members as member_services
from ..services import metadata as metadata_services
from ..services import moderation as moderation_services
from ..services import restore as restore_services
from .authentication import LegacyTokenAuthentication, principal_of
from .serializers import (
    DirectoryQuerySerializer,
    ForkSerializer,
    ImageUploadSerializer,
    LinkDetailSerializer,
    ListDetailSerializer,
    ListWriteSerializer,
    MemberAddSerializer,
    MemberRoleSerializer,
    MemberSerializer,
    MoveToListSerializer,
    ReorderSerializer,
    ReportSerializer,
)

IF_MATCH = OpenApiParameter(
    "If-Match",
    str,
    OpenApiParameter.HEADER,
    required=False,
    description='The list\'s ETag ("r{head_revision}") the change is based on. If the list '
    "changed since, the request fails with 412 `revision_mismatch` and changes nothing.",
)
IDEMPOTENCY_KEY = OpenApiParameter(
    "Idempotency-Key",
    str,
    OpenApiParameter.HEADER,
    required=False,
    description="A UUID per user action. Retrying with the same key returns the same resource.",
)
NOT_AN_IMAGE = OpenApiResponse(description="Not an accepted image, or over 2 MB.")
ERRORS = {
    401: OpenApiResponse(description="Sign-in (or the list's owner token) required."),
    403: OpenApiResponse(description="Not allowed for this user."),
    404: OpenApiResponse(description="No such list, or not visible to you."),
    410: OpenApiResponse(description="The list has expired."),
    412: OpenApiResponse(description="If-Match: the list changed since (revision_mismatch)."),
}


class ListPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


CODE = OpenApiParameter("code", str, OpenApiParameter.PATH, description="The list's code.")


@extend_schema_view(
    retrieve=extend_schema(parameters=[CODE]),
    partial_update=extend_schema(parameters=[CODE]),
    destroy=extend_schema(parameters=[CODE]),
    rotate_token=extend_schema(parameters=[CODE]),
    fork=extend_schema(parameters=[CODE]),
    restore=extend_schema(parameters=[CODE]),
    claim=extend_schema(parameters=[CODE]),
    reorder=extend_schema(parameters=[CODE]),
    report=extend_schema(parameters=[CODE]),
)
class ListViewSet(viewsets.ViewSet):
    # The owner-token authenticator comes first so 401 answers name the Bearer scheme it
    # accepts; requests without a token fall through to the session (with CSRF checks).
    authentication_classes = [LegacyTokenAuthentication, SessionAuthentication]
    permission_classes = []  # decided by the policy, per list
    throttle_classes = [WriteRateThrottle]  # unsafe methods only, per user or client IP
    pagination_class = ListPagination  # used by `list`; also tells OpenAPI the response shape
    lookup_url_kwarg = "code"

    @property
    def throttle_scope(self) -> str:
        scopes = {
            "create": "list_create",
            "fork": "list_create",
            "restore": "restore",
            "report": "report",
        }
        return scopes.get(self.action, "list_manage")

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "role",
                str,
                enum=[r.value for r in Role],
                required=False,
                description="Only lists where you have this role.",
            )
        ],
        responses={200: ListDetailSerializer(many=True), 401: ERRORS[401]},
    )
    def list(self, request):
        """Lists you own or are a member of, most recently changed first."""
        principal = principal_of(request)
        if principal.user is None:
            raise errors.AuthenticationRequired("Sign in to see your lists.")
        role = request.query_params.get("role")
        if role is not None and role not in {r.value for r in Role}:
            raise serializers.ValidationError({"role": ["Use owner, editor or viewer."]})
        lists = selectors.lists_of(principal.user, role=Role(role) if role else None)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(lists, request, view=self)
        context = {
            "access": {lst.pk: selectors.access_in_listing(principal.user, lst) for lst in page},
            "fork_sources": selectors.fork_sources(principal.user, page),
        }
        data = ListDetailSerializer(page, many=True, context=context).data
        return paginator.get_paginated_response(data)

    @extend_schema(
        request=ListWriteSerializer,
        parameters=[IDEMPOTENCY_KEY],
        responses={201: ListDetailSerializer, 200: ListDetailSerializer, 401: ERRORS[401]},
    )
    def create(self, request):
        """Create a list you own. New lists are private unless you choose otherwise."""
        principal = principal_of(request)
        if principal.user is None:
            raise errors.AuthenticationRequired("Sign in to create lists.")
        serializer = ListWriteSerializer(
            data=request.data, context={"email_verified": principal.email_verified}
        )
        serializer.is_valid(raise_exception=True)
        shared_list, created = services.create_list(
            principal, creation_key=_idempotency_key(request), **serializer.validated_data
        )
        return self._detail(
            principal, shared_list.public_code, status.HTTP_201_CREATED if created else 200
        )

    @extend_schema(responses={200: ListDetailSerializer, 404: ERRORS[404], 410: ERRORS[410]})
    def retrieve(self, request, code=None):
        return self._detail(principal_of(request), code)

    @extend_schema(
        request=ListWriteSerializer(partial=True),
        parameters=[IF_MATCH],
        responses={200: ListDetailSerializer, **ERRORS},
    )
    def partial_update(self, request, code=None):
        """Content (title, description) needs edit rights; settings need the owner."""
        principal = principal_of(request)
        shared_list, _ = selectors.get_list_for(principal, code)
        serializer = ListWriteSerializer(
            data=request.data,
            partial=True,
            context={"email_verified": principal.email_verified},
        )
        serializer.is_valid(raise_exception=True)
        services.update_list(
            principal,
            shared_list.pk,
            dict(serializer.validated_data),
            expected_head=if_match(request),
        )
        return self._detail(principal, code)

    @extend_schema(responses={204: None, **ERRORS})
    def destroy(self, request, code=None):
        principal = principal_of(request)
        shared_list, _ = selectors.get_list_for(principal, code)
        services.delete_list(principal, shared_list.pk)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=None, responses={200: OwnerTokenSerializer, **ERRORS})
    @action(detail=True, methods=["post"], url_path="rotate-token")
    def rotate_token(self, request, code=None):
        """Replace a legacy list's owner token (V1 behaviour); the old one stops working."""
        principal = principal_of(request)
        shared_list, _ = selectors.get_list_for(principal, code)
        owner_token = services.rotate_owner_token(principal, shared_list.pk)
        return Response(OwnerTokenSerializer({"owner_token": owner_token}).data)

    @extend_schema(request=None, responses={200: ListDetailSerializer, **ERRORS})
    @action(detail=True, methods=["post"])
    def claim(self, request, code=None):
        """Add a legacy list to your account: sign in and send its owner token as a Bearer
        header. The token stops working; expiry and visibility stay as they were."""
        principal = principal_of(request)
        shared_list, _ = selectors.get_list_for(principal, code)
        services.claim_list(principal, shared_list.pk)
        # The token is retired now; describe the list as the new owner sees it.
        return self._detail(selectors.Principal(user=principal.user), code)

    @extend_schema(
        request=ForkSerializer,
        parameters=[IDEMPOTENCY_KEY],
        responses={201: ListDetailSerializer, 200: ListDetailSerializer, **ERRORS},
    )
    @action(detail=True, methods=["post"])
    def fork(self, request, code=None):
        """Make a copy: a new private list you own, with this list's title, description, image
        and links (new short URLs). It's independent: later changes to either list don't reach
        the other. Allowed to the owner, and to anyone signed in who can view the list when its
        owner allows copies. Retrying with the same `Idempotency-Key` returns the first copy."""
        principal = principal_of(request)
        serializer = ForkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fork, created = fork_services.fork_list(
            principal,
            code,
            title=serializer.validated_data.get("title"),
            creation_key=_idempotency_key(request),
        )
        return self._detail(
            principal, fork.public_code, status.HTTP_201_CREATED if created else 200
        )

    @extend_schema(
        request=ReorderSerializer,
        parameters=[IF_MATCH],
        responses={200: LinkDetailSerializer(many=True), **ERRORS},
    )
    @action(detail=True, methods=["post"])
    def reorder(self, request, code=None):
        """Move one link to a new place. Applied to the current order under the list's lock, so
        concurrent moves never overwrite each other. Answers with the links in their new order."""
        principal = principal_of(request)
        shared_list, _ = selectors.get_list_for(principal, code)
        serializer = ReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        link_services.move_link(
            principal,
            shared_list.pk,
            serializer.validated_data["link"],
            serializer.validated_data["to_index"],
            expected_head=if_match(request),
        )
        links = selectors.links_with_short_codes(shared_list)
        return with_etag(
            Response(LinkDetailSerializer(links, many=True).data),
            selectors.head_revision_of(shared_list),
        )

    @extend_schema(
        request=RestoreSerializer,
        parameters=[
            OpenApiParameter(
                "If-Match",
                str,
                OpenApiParameter.HEADER,
                required=True,
                description='The list\'s current ETag ("r{head_revision}").',
            )
        ],
        responses={
            200: RestoreResultSerializer,
            428: OpenApiResponse(description="If-Match is missing."),
            **ERRORS,
        },
    )
    @action(detail=True, methods=["post"])
    def restore(self, request, code=None):
        """Make the list's content what it was at a revision: deleted links come back with the
        same short URLs, links added since are deleted, the order and the title come back.
        This writes a new revision; history is never rewritten. Settings stay as they are."""
        principal = principal_of(request)
        shared_list, _ = selectors.get_list_for(principal, code)
        serializer = RestoreSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        head, changed = restore_services.restore_revision(
            principal,
            shared_list.pk,
            serializer.validated_data["revision"],
            expected_head=if_match(request),
        )
        data = RestoreResultSerializer({"revision": head, "changed": changed}).data
        return with_etag(Response(data), head)

    @extend_schema(
        request=ReportSerializer,
        responses={
            202: OpenApiResponse(description="The operator has been told."),
            503: OpenApiResponse(description="The report couldn't be sent; try again later."),
            **ERRORS,
        },
    )
    @action(detail=True, methods=["post"])
    def report(self, request, code=None):
        """Report a list to the operator, for example phishing or spam. Anyone who can view
        the list may, signed in or not, except its owner. Rate-limited per user or IP."""
        principal = principal_of(request)
        serializer = ReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        moderation_services.report_list(principal, code, **serializer.validated_data)
        return Response(status=status.HTTP_202_ACCEPTED)

    def _detail(self, principal, code: str, status_code: int = 200) -> Response:
        shared_list, access = selectors.get_list_for(principal, code)
        data = ListDetailSerializer(
            shared_list, context=detail_context(principal, shared_list, access)
        ).data
        return with_etag(Response(data, status=status_code), shared_list.head_revision)


LINK_ID = OpenApiParameter("link_id", uuid.UUID, OpenApiParameter.PATH)


@extend_schema_view(
    list=extend_schema(parameters=[CODE]),
    create=extend_schema(parameters=[CODE]),
    partial_update=extend_schema(parameters=[CODE, LINK_ID]),
    destroy=extend_schema(parameters=[CODE, LINK_ID]),
)
class LinkViewSet(viewsets.ViewSet):
    """/api/v2/lists/{code}/links/: live links in their stored order.

    Editors and owners (session), or a legacy list's owner token (Bearer), may change links.
    Deleting keeps a tombstone: the link disappears and its short URL answers 404.
    """

    authentication_classes = [LegacyTokenAuthentication, SessionAuthentication]
    permission_classes = []
    throttle_classes = [WriteRateThrottle]
    pagination_class = ListPagination

    @property
    def throttle_scope(self) -> str:
        return "metadata_refresh" if self.action == "refresh_metadata" else "list_manage"

    @extend_schema(responses={200: LinkDetailSerializer(many=True), 404: ERRORS[404]})
    def list(self, request, code=None):
        shared_list, _ = selectors.get_list_for(principal_of(request), code)
        paginator = self.pagination_class()
        links = selectors.links_with_short_codes(shared_list)
        page = paginator.paginate_queryset(links, request, view=self)
        response = paginator.get_paginated_response(LinkDetailSerializer(page, many=True).data)
        return with_etag(response, shared_list.head_revision)

    @extend_schema(
        request=LinkDetailSerializer,
        parameters=[IDEMPOTENCY_KEY, IF_MATCH],
        responses={201: LinkDetailSerializer, 200: LinkDetailSerializer, **ERRORS},
    )
    def create(self, request, code=None):
        """Append a link, or insert it at `position`. Retrying with the same
        `Idempotency-Key` returns the first link (200) instead of adding another."""
        principal = principal_of(request)
        shared_list, _ = selectors.get_list_for(principal, code)
        serializer = LinkDetailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        link, created = link_services.add_link(
            principal,
            shared_list.pk,
            creation_key=_idempotency_key(request),
            expected_head=if_match(request),
            **serializer.validated_data,
        )
        data = LinkDetailSerializer(selectors.get_link(shared_list, link.pk)).data
        response = Response(data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        return with_etag(response, selectors.head_revision_of(shared_list))

    @extend_schema(
        request=LinkDetailSerializer,
        parameters=[IF_MATCH],
        responses={200: LinkDetailSerializer, **ERRORS},
    )
    def partial_update(self, request, code=None, link_id=None):
        principal = principal_of(request)
        shared_list, _ = selectors.get_list_for(principal, code)
        serializer = LinkDetailSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        link_services.update_link(
            principal,
            shared_list.pk,
            link_id,
            dict(serializer.validated_data),
            expected_head=if_match(request),
        )
        data = LinkDetailSerializer(selectors.get_link(shared_list, link_id)).data
        return with_etag(Response(data), selectors.head_revision_of(shared_list))

    @extend_schema(parameters=[IF_MATCH], responses={204: None, **ERRORS})
    def destroy(self, request, code=None, link_id=None):
        principal = principal_of(request)
        shared_list, _ = selectors.get_list_for(principal, code)
        link_services.delete_link(
            principal, shared_list.pk, link_id, expected_head=if_match(request)
        )
        return with_etag(
            Response(status=status.HTTP_204_NO_CONTENT), selectors.head_revision_of(shared_list)
        )

    @extend_schema(
        parameters=[CODE, LINK_ID, IF_MATCH],
        request=MoveToListSerializer,
        responses={201: LinkDetailSerializer, **ERRORS},
    )
    def move_to_list(self, request, code=None, link_id=None):
        """Move a link to the end of another list you can edit. It is copied there with a new
        short URL and deleted here (its old short URL answers 404)."""
        principal = principal_of(request)
        source, _ = selectors.get_list_for(principal, code)
        serializer = MoveToListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target, _ = selectors.get_list_for(principal, serializer.validated_data["list"])
        copy = link_services.move_link_to_list(
            principal, source.pk, link_id, target.pk, expected_head=if_match(request)
        )
        data = LinkDetailSerializer(selectors.get_link(target, copy.pk)).data
        # The ETag is the source list's: the one the request was made on.
        return with_etag(
            Response(data, status=status.HTTP_201_CREATED), selectors.head_revision_of(source)
        )

    @extend_schema(
        parameters=[CODE, LINK_ID],
        request=None,
        responses={
            202: None,
            409: OpenApiResponse(description="Fetching is turned off (metadata_disabled)."),
            429: OpenApiResponse(description="Refreshed less than an hour ago."),
            **ERRORS,
        },
    )
    def refresh_metadata(self, request, code=None, link_id=None):
        """Fetch the link's page again for its title, description and icon. Editors; at most
        once an hour per link. Answers at once (202); `metadata_status` shows the result."""
        principal = principal_of(request)
        shared_list, _ = selectors.get_list_for(principal, code)
        metadata_services.refresh(principal, shared_list.pk, link_id)
        return Response(status=status.HTTP_202_ACCEPTED)


class ImageUploadViewSet(viewsets.ViewSet):
    """Uploads: one multipart `file`, re-encoded (docs/v2/adr/ADR-012). Editors and owners
    only (an account is needed: an edit link can't upload). Own rate limit, `upload`."""

    authentication_classes = [LegacyTokenAuthentication, SessionAuthentication]
    permission_classes = []
    parser_classes = [MultiPartParser]
    throttle_classes = [WriteRateThrottle]
    throttle_scope = "upload"

    @staticmethod
    def _file(request) -> bytes:
        serializer = ImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data["file"]
        # One byte past the limit is enough for the pipeline to refuse it.
        return upload.read(MAX_UPLOAD_BYTES + 1)


@extend_schema_view(
    update=extend_schema(
        parameters=[CODE],
        request={"multipart/form-data": ImageUploadSerializer},
        responses={200: ListDetailSerializer, 400: NOT_AN_IMAGE, **ERRORS},
    ),
    destroy=extend_schema(parameters=[CODE], responses={204: None, **ERRORS}),
)
class ListImageViewSet(ImageUploadViewSet):
    """/api/v2/lists/{code}/image/: the list's image, shrunk to fit 512×512."""

    def update(self, request, code=None):
        principal = principal_of(request)
        shared_list, _ = selectors.get_list_for(principal, code)
        media_services.set_list_image(principal, shared_list.pk, self._file(request))
        shared_list, access = selectors.get_list_for(principal, code)
        data = ListDetailSerializer(
            shared_list, context=detail_context(principal, shared_list, access)
        ).data
        return Response(data)

    def destroy(self, request, code=None):
        principal = principal_of(request)
        shared_list, _ = selectors.get_list_for(principal, code)
        media_services.set_list_image(principal, shared_list.pk, None)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    update=extend_schema(
        parameters=[CODE, LINK_ID, IF_MATCH],
        request={"multipart/form-data": ImageUploadSerializer},
        responses={200: LinkDetailSerializer, 400: NOT_AN_IMAGE, **ERRORS},
    ),
    destroy=extend_schema(parameters=[CODE, LINK_ID, IF_MATCH], responses={204: None, **ERRORS}),
)
class LinkIconViewSet(ImageUploadViewSet):
    """/api/v2/lists/{code}/links/{id}/icon/: a link's own icon, shrunk to fit 128×128."""

    def update(self, request, code=None, link_id=None):
        principal = principal_of(request)
        shared_list, _ = selectors.get_list_for(principal, code)
        media_services.set_link_icon(
            principal,
            shared_list.pk,
            link_id,
            self._file(request),
            expected_head=if_match(request),
        )
        data = LinkDetailSerializer(selectors.get_link(shared_list, link_id)).data
        return with_etag(Response(data), selectors.head_revision_of(shared_list))

    def destroy(self, request, code=None, link_id=None):
        principal = principal_of(request)
        shared_list, _ = selectors.get_list_for(principal, code)
        media_services.set_link_icon(
            principal, shared_list.pk, link_id, None, expected_head=if_match(request)
        )
        return with_etag(
            Response(status=status.HTTP_204_NO_CONTENT), selectors.head_revision_of(shared_list)
        )


NUMBER = OpenApiParameter("number", int, OpenApiParameter.PATH, description="Revision number.")


@extend_schema_view(
    list=extend_schema(parameters=[CODE], responses={200: RevisionSerializer(many=True), **ERRORS}),
    retrieve=extend_schema(
        parameters=[CODE, NUMBER], responses={200: RevisionDetailSerializer, **ERRORS}
    ),
)
class RevisionViewSet(viewsets.ViewSet):
    """/api/v2/lists/{code}/revisions/: a list's history, newest first. Editors, owners and a
    legacy list's edit link only: history can hold links an owner deliberately removed."""

    authentication_classes = [LegacyTokenAuthentication, SessionAuthentication]
    permission_classes = []
    pagination_class = ListPagination

    def list(self, request, code=None):
        shared_list = self._history_of(request, code)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(
            version_selectors.revisions_of(shared_list), request, view=self
        )
        response = paginator.get_paginated_response(RevisionSerializer(page, many=True).data)
        return with_etag(response, shared_list.head_revision)

    def retrieve(self, request, code=None, number=None):
        shared_list = self._history_of(request, code)
        revision = version_selectors.get_revision(shared_list, int(number))
        return Response(RevisionDetailSerializer(revision).data)

    @staticmethod
    def _history_of(request, code):
        principal = principal_of(request)
        shared_list, access = selectors.get_list_for(principal, code)
        if not can(access.actor, Action.VIEW_HISTORY, access.facts):
            raise services.denied(principal, "Only the list's editors can see its history.")
        return shared_list


USER_ID = OpenApiParameter("user_id", uuid.UUID, OpenApiParameter.PATH)


@extend_schema_view(
    list=extend_schema(parameters=[CODE]),
    create=extend_schema(parameters=[CODE]),
    partial_update=extend_schema(parameters=[CODE, USER_ID]),
    destroy=extend_schema(parameters=[CODE, USER_ID]),
)
class MemberViewSet(viewsets.ViewSet):
    """/api/v2/lists/{code}/members/: who an account list is shared with.

    The owner and editors may read it. Only the owner adds people (by the email address of
    an existing, verified account), changes roles and removes people; members may leave.
    """

    authentication_classes = [SessionAuthentication]  # legacy lists have no members
    permission_classes = []
    throttle_classes = [WriteRateThrottle]
    pagination_class = ListPagination

    @property
    def throttle_scope(self) -> str:
        # Adding by email can probe which addresses have accounts, so it has its own limit.
        return "member_add" if self.action == "create" else "list_manage"

    @extend_schema(responses={200: MemberSerializer(many=True), **ERRORS})
    def list(self, request, code=None):
        principal = self._signed_in(request)
        shared_list, access = selectors.get_list_for(principal, code)
        paginator = self.pagination_class()
        members = selectors.members_of(shared_list, access)
        page = paginator.paginate_queryset(members, request, view=self)
        data = MemberSerializer(page, many=True, context={"user_id": principal.user.pk}).data
        return paginator.get_paginated_response(data)

    @extend_schema(request=MemberAddSerializer, responses={201: MemberSerializer, **ERRORS})
    def create(self, request, code=None):
        principal = self._signed_in(request)
        shared_list, _ = selectors.get_list_for(principal, code)
        serializer = MemberAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = member_services.add_member(
            principal,
            shared_list.pk,
            email=serializer.validated_data["email"],
            role=Role(serializer.validated_data["role"]),
        )
        data = MemberSerializer(membership, context={"user_id": principal.user.pk}).data
        return Response(data, status=status.HTTP_201_CREATED)

    @extend_schema(request=MemberRoleSerializer, responses={200: MemberSerializer, **ERRORS})
    def partial_update(self, request, code=None, user_id=None):
        principal = self._signed_in(request)
        shared_list, _ = selectors.get_list_for(principal, code)
        serializer = MemberRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = member_services.change_role(
            principal, shared_list.pk, user_id, Role(serializer.validated_data["role"])
        )
        return Response(MemberSerializer(membership, context={"user_id": principal.user.pk}).data)

    @extend_schema(responses={204: None, **ERRORS})
    def destroy(self, request, code=None, user_id=None):
        """Remove someone (owner), or leave the list (your own user id)."""
        principal = self._signed_in(request)
        shared_list, _ = selectors.get_list_for(principal, code)
        member_services.remove_member(principal, shared_list.pk, user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def _signed_in(request) -> selectors.Principal:
        principal = principal_of(request)
        if principal.user is None:
            raise errors.AuthenticationRequired("Sign in to see who a list is shared with.")
        return principal


class DirectoryListViewSet(viewsets.ViewSet):
    """/api/v2/directory/lists/: public lists, searchable by text and tags. Anyone may read
    it; signed-in readers see their own role on lists they belong to. Rate-limited per IP."""

    authentication_classes = [SessionAuthentication]
    permission_classes = []
    throttle_classes = [ReadRateThrottle]
    throttle_scope = "directory"
    pagination_class = ListPagination

    @extend_schema(
        parameters=[DirectoryQuerySerializer],
        responses={200: ListDetailSerializer(many=True)},
    )
    def list(self, request):
        params = DirectoryQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        user = principal_of(request).user
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(
            selectors.public_lists(user, **params.validated_data), request, view=self
        )
        context = {
            "access": {lst.pk: selectors.access_in_listing(user, lst) for lst in page},
            "fork_sources": selectors.fork_sources(user, page),
        }
        data = ListDetailSerializer(page, many=True, context=context).data
        return paginator.get_paginated_response(data)


def detail_context(principal, shared_list, access) -> dict:
    """The serializer context for one list as `principal` sees it."""
    return {
        "access": {shared_list.pk: access},
        "fork_sources": selectors.fork_sources(principal.user, [shared_list]),
    }


def _idempotency_key(request) -> uuid.UUID | None:
    value = request.headers.get("Idempotency-Key")
    if value is None:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        raise serializers.ValidationError({"Idempotency-Key": ["Must be a UUID."]}) from None


# Revisions as HTTP preconditions (docs/v2/09-API-DESIGN.md#concurrency-preconditions).
_IF_MATCH = re.compile(r'\s*"r(\d+)"\s*')  # strong comparison: a weak ETag never matches


def if_match(request) -> int | None:
    """The revision an If-Match header names: None if absent or `*`. A value that isn't one
    of our ETags can't match the current state, so it fails like a stale one."""
    value = request.headers.get("If-Match")
    if value is None or value.strip() == "*":
        return None
    match = _IF_MATCH.fullmatch(value)
    if match is None:
        raise errors.RevisionMismatch('If-Match must be an ETag such as "r12".')
    return int(match.group(1))


def with_etag(response: Response, head_revision: int) -> Response:
    response["ETag"] = f'"r{head_revision}"'
    return response
