"""/api/v2/groups/ (docs/v2/09-API-DESIGN.md#groups).

Views do HTTP only. Groups are for accounts: a legacy edit link grants nothing here, so only
the session authenticates. A group's lists are always the ones it shows the requester,
filtered in SQL (docs/v2/12-AUTHORIZATION.md#which-lists-a-group-shows-to-a-viewer).
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
from rest_framework.response import Response

from apps.accounts.authentication import SessionAuthentication
from apps.common import errors
from apps.sharing.permissions import WriteRateThrottle
from apps.sharing.policy import Role
from apps.sharing.selectors import Principal, access_in_listing
from apps.sharing.v2.authentication import principal_of
from apps.sharing.v2.serializers import (
    ImageUploadSerializer,
    MemberAddSerializer,
    MemberRoleSerializer,
)
from apps.sharing.v2.views import NOT_AN_IMAGE, ImageUploadViewSet, ListPagination

from . import selectors, services
from .selectors import GroupAccess, group_actor
from .serializers import (
    AddListSerializer,
    GroupDetailSerializer,
    GroupListSerializer,
    GroupMemberSerializer,
    GroupReorderSerializer,
    GroupWriteSerializer,
)

ERRORS = {
    401: OpenApiResponse(description="Sign-in required."),
    403: OpenApiResponse(description="Not allowed for this user."),
    404: OpenApiResponse(description="No such group, or not visible to you."),
}
CODE = OpenApiParameter("code", str, OpenApiParameter.PATH, description="The group's code.")
LIST_CODE = OpenApiParameter("list_code", str, OpenApiParameter.PATH, description="A list's code.")
USER_ID = OpenApiParameter("user_id", uuid.UUID, OpenApiParameter.PATH)


def _signed_in(request, message: str) -> Principal:
    principal = principal_of(request)
    if principal.user is None:
        raise errors.AuthenticationRequired(message)
    return principal


def group_detail(principal: Principal, code: str, status_code: int = 200) -> Response:
    group, access = selectors.get_group_for(principal, code)
    group.list_count = selectors.entries_for(principal, group).count()
    data = GroupDetailSerializer(group, context={"access": {group.pk: access}}).data
    return Response(data, status=status_code)


def group_lists(principal: Principal, group) -> Response:
    """The lists the group shows the principal, in order: all of them (at most 100)."""
    lists = list(selectors.lists_in(principal, group))
    access = {lst.pk: access_in_listing(principal.user, lst) for lst in lists}
    data = GroupListSerializer(lists, many=True, context={"access": access, "group": group}).data
    return Response(data)


@extend_schema_view(
    retrieve=extend_schema(parameters=[CODE]),
    partial_update=extend_schema(parameters=[CODE]),
    destroy=extend_schema(parameters=[CODE]),
    reorder=extend_schema(parameters=[CODE]),
)
class GroupViewSet(viewsets.ViewSet):
    authentication_classes = [SessionAuthentication]
    permission_classes = []  # decided by the policy, per group
    throttle_classes = [WriteRateThrottle]
    pagination_class = ListPagination
    lookup_url_kwarg = "code"

    @property
    def throttle_scope(self) -> str:
        return "group_create" if self.action == "create" else "group_manage"

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "role",
                str,
                enum=[r.value for r in Role],
                required=False,
                description="Only groups where you have this role.",
            )
        ],
        responses={200: GroupDetailSerializer(many=True), 401: ERRORS[401]},
    )
    def list(self, request):
        """Groups you own or are a member of, most recently changed first."""
        principal = _signed_in(request, "Sign in to see your groups.")
        role = request.query_params.get("role")
        if role is not None and role not in {r.value for r in Role}:
            raise serializers.ValidationError({"role": ["Use owner, editor or viewer."]})
        groups = selectors.groups_of(principal.user, role=Role(role) if role else None)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(groups, request, view=self)
        actor = group_actor(principal)
        access = {
            group.pk: GroupAccess(actor, selectors.facts_in_listing(principal.user, group))
            for group in page
        }
        data = GroupDetailSerializer(page, many=True, context={"access": access}).data
        return paginator.get_paginated_response(data)

    @extend_schema(
        request=GroupWriteSerializer, responses={201: GroupDetailSerializer, 401: ERRORS[401]}
    )
    def create(self, request):
        """Create a group you own. New groups are private unless you choose otherwise."""
        principal = _signed_in(request, "Sign in to create groups.")
        serializer = GroupWriteSerializer(
            data=request.data, context={"email_verified": principal.email_verified}
        )
        serializer.is_valid(raise_exception=True)
        group = services.create_group(principal, **serializer.validated_data)
        return group_detail(principal, group.code, status.HTTP_201_CREATED)

    @extend_schema(responses={200: GroupDetailSerializer, 404: ERRORS[404]})
    def retrieve(self, request, code=None):
        return group_detail(principal_of(request), code)

    @extend_schema(
        request=GroupWriteSerializer(partial=True),
        responses={200: GroupDetailSerializer, **ERRORS},
    )
    def partial_update(self, request, code=None):
        """Title and description need edit rights; visibility needs the owner."""
        principal = principal_of(request)
        group, _ = selectors.get_group_for(principal, code)
        serializer = GroupWriteSerializer(
            data=request.data, partial=True, context={"email_verified": principal.email_verified}
        )
        serializer.is_valid(raise_exception=True)
        services.update_group(principal, group.pk, dict(serializer.validated_data))
        return group_detail(principal, code)

    @extend_schema(responses={204: None, **ERRORS})
    def destroy(self, request, code=None):
        """Delete the group. The lists in it are untouched."""
        principal = principal_of(request)
        group, _ = selectors.get_group_for(principal, code)
        services.delete_group(principal, group.pk)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request=GroupReorderSerializer,
        responses={200: GroupListSerializer(many=True), **ERRORS},
    )
    @action(detail=True, methods=["post"])
    def reorder(self, request, code=None):
        """Move one list to a new place among the lists you are shown. Lists hidden from you
        keep their places. Answers with the group's lists in their new order."""
        principal = principal_of(request)
        group, _ = selectors.get_group_for(principal, code)
        serializer = GroupReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.move_list(
            principal,
            group.pk,
            serializer.validated_data["list"],
            serializer.validated_data["to_index"],
        )
        return group_lists(principal, group)


@extend_schema_view(
    list=extend_schema(parameters=[CODE]),
    create=extend_schema(parameters=[CODE]),
    destroy=extend_schema(parameters=[CODE, LIST_CODE]),
)
class GroupListViewSet(viewsets.ViewSet):
    """/api/v2/groups/{code}/lists/: only the lists the group shows you, in order. Lists you
    may not see are left out entirely: no titles, placeholders or counts."""

    authentication_classes = [SessionAuthentication]
    permission_classes = []
    throttle_classes = [WriteRateThrottle]
    throttle_scope = "group_manage"

    @extend_schema(responses={200: GroupListSerializer(many=True), 404: ERRORS[404]})
    def list(self, request, code=None):
        principal = principal_of(request)
        group, _ = selectors.get_group_for(principal, code)
        return group_lists(principal, group)

    @extend_schema(
        request=AddListSerializer,
        responses={
            201: GroupListSerializer,
            409: OpenApiResponse(description="The list is in the group already."),
            410: OpenApiResponse(description="The list has expired."),
            **ERRORS,
        },
    )
    def create(self, request, code=None):
        """Add a list at the end. You need edit rights on the group, and the list must be one
        you could share yourself: one you own or edit, or a public one."""
        principal = principal_of(request)
        group, _ = selectors.get_group_for(principal, code)
        serializer = AddListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = services.add_list(principal, group.pk, serializer.validated_data["list"])
        added = next(
            lst for lst in selectors.lists_in(principal, group) if lst.pk == entry.shared_list_id
        )
        context = {
            "access": {added.pk: access_in_listing(principal.user, added)},
            "group": group,
        }
        return Response(GroupListSerializer(added, context=context).data, status=201)

    @extend_schema(responses={204: None, **ERRORS})
    def destroy(self, request, code=None, list_code=None):
        """Take a list out of the group. The list itself is untouched."""
        principal = principal_of(request)
        group, _ = selectors.get_group_for(principal, code)
        services.remove_list(principal, group.pk, list_code)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    update=extend_schema(
        parameters=[CODE],
        request={"multipart/form-data": ImageUploadSerializer},
        responses={200: GroupDetailSerializer, 400: NOT_AN_IMAGE, **ERRORS},
    ),
    destroy=extend_schema(parameters=[CODE], responses={204: None, **ERRORS}),
)
class GroupImageViewSet(ImageUploadViewSet):
    """/api/v2/groups/{code}/image/: the group's image, shrunk to fit 512×512."""

    authentication_classes = [SessionAuthentication]

    def update(self, request, code=None):
        principal = principal_of(request)
        group, _ = selectors.get_group_for(principal, code)
        services.set_group_image(principal, group.pk, self._file(request))
        return group_detail(principal, code)

    def destroy(self, request, code=None):
        principal = principal_of(request)
        group, _ = selectors.get_group_for(principal, code)
        services.set_group_image(principal, group.pk, None)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    list=extend_schema(parameters=[CODE]),
    create=extend_schema(parameters=[CODE]),
    partial_update=extend_schema(parameters=[CODE, USER_ID]),
    destroy=extend_schema(parameters=[CODE, USER_ID]),
)
class GroupMemberViewSet(viewsets.ViewSet):
    """/api/v2/groups/{code}/members/: who a group is shared with. As for lists: the owner
    and editors may read it, the owner adds people by the email address of a verified
    account, changes roles and removes people, and members may leave. A group role grants
    nothing on the lists in the group."""

    authentication_classes = [SessionAuthentication]
    permission_classes = []
    throttle_classes = [WriteRateThrottle]
    pagination_class = ListPagination

    @property
    def throttle_scope(self) -> str:
        return "member_add" if self.action == "create" else "group_manage"

    @extend_schema(responses={200: GroupMemberSerializer(many=True), **ERRORS})
    def list(self, request, code=None):
        principal = _signed_in(request, "Sign in to see who a group is shared with.")
        group, access = selectors.get_group_for(principal, code)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(selectors.members_of(group, access), request, view=self)
        data = GroupMemberSerializer(page, many=True, context={"user_id": principal.user.pk}).data
        return paginator.get_paginated_response(data)

    @extend_schema(request=MemberAddSerializer, responses={201: GroupMemberSerializer, **ERRORS})
    def create(self, request, code=None):
        principal = _signed_in(request, "Sign in to add people to a group.")
        group, _ = selectors.get_group_for(principal, code)
        serializer = MemberAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = services.add_member(
            principal,
            group.pk,
            email=serializer.validated_data["email"],
            role=Role(serializer.validated_data["role"]),
        )
        data = GroupMemberSerializer(membership, context={"user_id": principal.user.pk}).data
        return Response(data, status=status.HTTP_201_CREATED)

    @extend_schema(request=MemberRoleSerializer, responses={200: GroupMemberSerializer, **ERRORS})
    def partial_update(self, request, code=None, user_id=None):
        principal = _signed_in(request, "Sign in to change roles.")
        group, _ = selectors.get_group_for(principal, code)
        serializer = MemberRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = services.change_role(
            principal, group.pk, user_id, Role(serializer.validated_data["role"])
        )
        context = {"user_id": principal.user.pk}
        return Response(GroupMemberSerializer(membership, context=context).data)

    @extend_schema(responses={204: None, **ERRORS})
    def destroy(self, request, code=None, user_id=None):
        """Remove someone (owner), or leave the group (your own user id)."""
        principal = _signed_in(request, "Sign in to change who a group is shared with.")
        group, _ = selectors.get_group_for(principal, code)
        services.remove_member(principal, group.pk, user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
