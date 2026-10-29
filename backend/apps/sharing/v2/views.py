"""/api/v2/lists/: lists with accounts and visibility (docs/v2/09-API-DESIGN.md#lists).

Views do HTTP only. Who may do what is decided by the policy, through selectors (reads) and
services (writes, re-checked under the row lock).
"""

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
from rest_framework.response import Response

from apps.accounts.authentication import SessionAuthentication
from apps.common import errors

from .. import selectors
from ..permissions import WriteRateThrottle
from ..policy import Role
from ..serializers import OwnerTokenSerializer
from ..services import links as link_services
from ..services import lists as services
from ..services import members as member_services
from .authentication import LegacyTokenAuthentication, principal_of
from .serializers import (
    LinkDetailSerializer,
    ListDetailSerializer,
    ListWriteSerializer,
    MemberAddSerializer,
    MemberRoleSerializer,
    MemberSerializer,
)

IDEMPOTENCY_KEY = OpenApiParameter(
    "Idempotency-Key",
    str,
    OpenApiParameter.HEADER,
    required=False,
    description="A UUID per user action. Retrying with the same key returns the same resource.",
)
ERRORS = {
    401: OpenApiResponse(description="Sign-in (or the list's owner token) required."),
    403: OpenApiResponse(description="Not allowed for this user."),
    404: OpenApiResponse(description="No such list, or not visible to you."),
    410: OpenApiResponse(description="The list has expired."),
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
    claim=extend_schema(parameters=[CODE]),
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
        return "list_create" if self.action == "create" else "list_manage"

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
        access = {lst.pk: selectors.access_in_listing(principal.user, lst) for lst in page}
        data = ListDetailSerializer(page, many=True, context={"access": access}).data
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
        services.update_list(principal, shared_list.pk, dict(serializer.validated_data))
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

    def _detail(self, principal, code: str, status_code: int = 200) -> Response:
        shared_list, access = selectors.get_list_for(principal, code)
        data = ListDetailSerializer(shared_list, context={"access": {shared_list.pk: access}}).data
        return Response(data, status=status_code)


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
    throttle_scope = "list_manage"
    pagination_class = ListPagination

    @extend_schema(responses={200: LinkDetailSerializer(many=True), 404: ERRORS[404]})
    def list(self, request, code=None):
        shared_list, _ = selectors.get_list_for(principal_of(request), code)
        paginator = self.pagination_class()
        links = selectors.links_with_short_codes(shared_list)
        page = paginator.paginate_queryset(links, request, view=self)
        return paginator.get_paginated_response(LinkDetailSerializer(page, many=True).data)

    @extend_schema(
        request=LinkDetailSerializer,
        parameters=[IDEMPOTENCY_KEY],
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
            **serializer.validated_data,
        )
        data = LinkDetailSerializer(selectors.get_link(shared_list, link.pk)).data
        return Response(data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @extend_schema(request=LinkDetailSerializer, responses={200: LinkDetailSerializer, **ERRORS})
    def partial_update(self, request, code=None, link_id=None):
        principal = principal_of(request)
        shared_list, _ = selectors.get_list_for(principal, code)
        serializer = LinkDetailSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        link_services.update_link(
            principal, shared_list.pk, link_id, dict(serializer.validated_data)
        )
        return Response(LinkDetailSerializer(selectors.get_link(shared_list, link_id)).data)

    @extend_schema(responses={204: None, **ERRORS})
    def destroy(self, request, code=None, link_id=None):
        principal = principal_of(request)
        shared_list, _ = selectors.get_list_for(principal, code)
        link_services.delete_link(principal, shared_list.pk, link_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


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


def _idempotency_key(request) -> uuid.UUID | None:
    value = request.headers.get("Idempotency-Key")
    if value is None:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        raise serializers.ValidationError({"Idempotency-Key": ["Must be a UUID."]}) from None
