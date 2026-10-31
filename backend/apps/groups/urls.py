from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    DirectoryGroupViewSet,
    DirectoryTagViewSet,
    GroupImageViewSet,
    GroupListViewSet,
    GroupMemberViewSet,
    GroupViewSet,
)

router = SimpleRouter()
router.register("groups", GroupViewSet, basename="v2-group")

lists = GroupListViewSet.as_view({"get": "list", "post": "create"})
group_list = GroupListViewSet.as_view({"delete": "destroy"})
members = GroupMemberViewSet.as_view({"get": "list", "post": "create"})
member = GroupMemberViewSet.as_view({"patch": "partial_update", "delete": "destroy"})
# An upload route: config.middleware.UPLOAD_PATH and nginx allow it a larger body.
image = GroupImageViewSet.as_view({"put": "update", "delete": "destroy"})

directory_groups = DirectoryGroupViewSet.as_view({"get": "list"})
directory_tags = DirectoryTagViewSet.as_view({"get": "list"})

urlpatterns = [
    path("directory/groups/", directory_groups, name="v2-directory-groups"),
    path("directory/tags/", directory_tags, name="v2-directory-tags"),
    *router.urls,
    path("groups/<str:code>/lists/", lists, name="v2-group-lists"),
    path("groups/<str:code>/lists/<str:list_code>/", group_list, name="v2-group-list"),
    path("groups/<str:code>/image/", image, name="v2-group-image"),
    path("groups/<str:code>/members/", members, name="v2-group-member-list"),
    path("groups/<str:code>/members/<uuid:user_id>/", member, name="v2-group-member-detail"),
]
