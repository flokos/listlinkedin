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
from ..serializers import OwnerTokenSerializer
from ..services import lists as services
from .authentication import LegacyTokenAuthentication, principal_of
from .serializers import ListDetailSerializer, ListWriteSerializer

IDEMPOTENCY_KEY = OpenApiParameter(
    "Idempotency-Key",
    str,
    OpenApiParameter.HEADER,
    required=False,
    description="A UUID per user action. Retrying with the same key returns the same list.",
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

    @extend_schema(responses={200: ListDetailSerializer(many=True), 401: ERRORS[401]})
    def list(self, request):
        """Lists you own or are a member of, most recently changed first."""
        principal = principal_of(request)
        if principal.user is None:
            raise errors.AuthenticationRequired("Sign in to see your lists.")
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(selectors.lists_of(principal.user), request, view=self)
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

    def _detail(self, principal, code: str, status_code: int = 200) -> Response:
        shared_list, access = selectors.get_list_for(principal, code)
        data = ListDetailSerializer(shared_list, context={"access": {shared_list.pk: access}}).data
        return Response(data, status=status_code)


def _idempotency_key(request) -> uuid.UUID | None:
    value = request.headers.get("Idempotency-Key")
    if value is None:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        raise serializers.ValidationError({"Idempotency-Key": ["Must be a UUID."]}) from None
