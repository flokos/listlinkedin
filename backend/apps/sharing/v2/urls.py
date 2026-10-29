from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import LinkViewSet, ListViewSet, MemberViewSet

router = SimpleRouter()
router.register("lists", ListViewSet, basename="v2-list")

links = LinkViewSet.as_view({"get": "list", "post": "create"})
link = LinkViewSet.as_view({"patch": "partial_update", "delete": "destroy"})
members = MemberViewSet.as_view({"get": "list", "post": "create"})
member = MemberViewSet.as_view({"patch": "partial_update", "delete": "destroy"})

urlpatterns = [
    *router.urls,
    path("lists/<str:code>/links/", links, name="v2-link-list"),
    path("lists/<str:code>/links/<uuid:link_id>/", link, name="v2-link-detail"),
    path("lists/<str:code>/members/", members, name="v2-member-list"),
    path("lists/<str:code>/members/<uuid:user_id>/", member, name="v2-member-detail"),
]
