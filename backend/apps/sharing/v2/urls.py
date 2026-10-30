from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    DirectoryListViewSet,
    LinkIconViewSet,
    LinkViewSet,
    ListImageViewSet,
    ListViewSet,
    MemberViewSet,
    RevisionViewSet,
)

router = SimpleRouter()
router.register("lists", ListViewSet, basename="v2-list")

links = LinkViewSet.as_view({"get": "list", "post": "create"})
link = LinkViewSet.as_view({"patch": "partial_update", "delete": "destroy"})
members = MemberViewSet.as_view({"get": "list", "post": "create"})
member = MemberViewSet.as_view({"patch": "partial_update", "delete": "destroy"})
move_link = LinkViewSet.as_view({"post": "move_to_list"})
refresh_metadata = LinkViewSet.as_view({"post": "refresh_metadata"})
# Upload routes: config.middleware.UPLOAD_PATH and nginx allow them larger bodies.
list_image = ListImageViewSet.as_view({"put": "update", "delete": "destroy"})
link_icon = LinkIconViewSet.as_view({"put": "update", "delete": "destroy"})

urlpatterns = [
    *router.urls,
    path(
        "directory/lists/", DirectoryListViewSet.as_view({"get": "list"}), name="v2-directory-lists"
    ),
    path("lists/<str:code>/links/", links, name="v2-link-list"),
    path("lists/<str:code>/links/<uuid:link_id>/", link, name="v2-link-detail"),
    path(
        "lists/<str:code>/links/<uuid:link_id>/move-to-list/",
        move_link,
        name="v2-link-move-to-list",
    ),
    path(
        "lists/<str:code>/links/<uuid:link_id>/refresh-metadata/",
        refresh_metadata,
        name="v2-link-refresh-metadata",
    ),
    path("lists/<str:code>/image/", list_image, name="v2-list-image"),
    path("lists/<str:code>/links/<uuid:link_id>/icon/", link_icon, name="v2-link-icon"),
    path(
        "lists/<str:code>/revisions/",
        RevisionViewSet.as_view({"get": "list"}),
        name="v2-revision-list",
    ),
    path(
        "lists/<str:code>/revisions/<int:number>/",
        RevisionViewSet.as_view({"get": "retrieve"}),
        name="v2-revision-detail",
    ),
    path("lists/<str:code>/members/", members, name="v2-member-list"),
    path("lists/<str:code>/members/<uuid:user_id>/", member, name="v2-member-detail"),
]
