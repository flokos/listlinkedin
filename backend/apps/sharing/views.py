from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from . import selectors, services
from .exceptions import Gone
from .permissions import IsListOwnerOrReadOnly, OwnerTokenAuthentication, WriteRateThrottle
from .serializers import (
    LinkSerializer,
    ListCreatedSerializer,
    ListSerializer,
    OwnerTokenSerializer,
)

PUBLIC = []  # OpenAPI: no authentication required
NOT_FOUND = OpenApiResponse(description="Unknown or already deleted list/link.")
GONE = OpenApiResponse(description="The list has expired.")
OWNER_ERRORS = {
    401: OpenApiResponse(description="Missing owner token."),
    403: OpenApiResponse(description="Owner token does not match this list."),
    404: NOT_FOUND,
    410: GONE,
}


class LinkPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class ListCreateView(APIView):
    throttle_classes = [WriteRateThrottle]
    throttle_scope = "list_create"

    @extend_schema(
        request=ListSerializer,
        responses={
            201: ListCreatedSerializer,
            400: OpenApiResponse(description="Invalid input."),
            410: OpenApiResponse(description="Retired: create lists with an account (v2)."),
        },
        auth=PUBLIC,
        summary="Create a list (returns the private owner token once)",
    )
    def post(self, request):
        # Creating lists needs an account since V2 (docs/v2/adr/ADR-011). The switch exists
        # only so test stacks can still create legacy lists; it goes at the legacy sunset.
        if not settings.LEGACY_LIST_CREATION:
            raise Gone("Creating lists now requires an account.")
        serializer = ListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shared_list, owner_token = services.create_list(**serializer.validated_data)
        shared_list.owner_token = owner_token
        return Response(ListCreatedSerializer(shared_list).data, status=status.HTTP_201_CREATED)


class OwnedListView(APIView):
    """Base for endpoints under /lists/{list_code}/: public reads, owner-only writes."""

    authentication_classes = [OwnerTokenAuthentication]
    permission_classes = [IsListOwnerOrReadOnly]
    throttle_classes = [WriteRateThrottle]
    throttle_scope = "list_manage"

    def get_list(self, list_code: str):
        shared_list = selectors.get_active_list(list_code)
        self.check_object_permissions(self.request, shared_list)
        return shared_list


class ListDetailView(OwnedListView):
    @extend_schema(responses={200: ListSerializer, 404: NOT_FOUND, 410: GONE}, auth=PUBLIC)
    def get(self, request, list_code):
        return Response(ListSerializer(self.get_list(list_code)).data)

    @extend_schema(request=ListSerializer, responses={200: ListSerializer, **OWNER_ERRORS})
    def patch(self, request, list_code):
        shared_list = self.get_list(list_code)
        serializer = ListSerializer(shared_list, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        title = serializer.validated_data.get("title", shared_list.title)
        return Response(ListSerializer(services.update_list(shared_list, title=title)).data)

    @extend_schema(responses={204: None, **OWNER_ERRORS})
    def delete(self, request, list_code):
        services.delete_list(self.get_list(list_code))
        return Response(status=status.HTTP_204_NO_CONTENT)


class OwnerTokenRotateView(OwnedListView):
    @extend_schema(
        request=None,
        responses={200: OwnerTokenSerializer, **OWNER_ERRORS},
        summary="Rotate the owner token (revokes the current one)",
    )
    def post(self, request, list_code):
        owner_token = services.rotate_owner_token(self.get_list(list_code))
        return Response(OwnerTokenSerializer({"owner_token": owner_token}).data)


class LinkCollectionView(OwnedListView):
    pagination_class = LinkPagination

    @extend_schema(
        responses={200: LinkSerializer(many=True), 404: NOT_FOUND, 410: GONE}, auth=PUBLIC
    )
    def get(self, request, list_code):
        links = selectors.links_with_short_codes(self.get_list(list_code))
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(links, request, view=self)
        return paginator.get_paginated_response(LinkSerializer(page, many=True).data)

    @extend_schema(request=LinkSerializer, responses={201: LinkSerializer, **OWNER_ERRORS})
    def post(self, request, list_code):
        shared_list = self.get_list(list_code)
        serializer = LinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        link = services.add_link(shared_list, **serializer.validated_data)
        return Response(
            LinkSerializer(selectors.get_link(shared_list, link.pk)).data,
            status=status.HTTP_201_CREATED,
        )


class LinkDetailView(OwnedListView):
    @extend_schema(request=LinkSerializer, responses={200: LinkSerializer, **OWNER_ERRORS})
    def patch(self, request, list_code, link_id):
        shared_list = self.get_list(list_code)
        serializer = LinkSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        services.update_link(shared_list, link_id, **serializer.validated_data)
        return Response(LinkSerializer(selectors.get_link(shared_list, link_id)).data)

    @extend_schema(responses={204: None, **OWNER_ERRORS})
    def delete(self, request, list_code, link_id):
        services.delete_link(self.get_list(list_code), link_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
