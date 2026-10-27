from django.urls import path

from . import views

urlpatterns = [
    path("lists/", views.ListCreateView.as_view(), name="list-create"),
    path("lists/<str:list_code>/", views.ListDetailView.as_view(), name="list-detail"),
    path(
        "lists/<str:list_code>/rotate-token/",
        views.OwnerTokenRotateView.as_view(),
        name="list-rotate-token",
    ),
    path("lists/<str:list_code>/links/", views.LinkCollectionView.as_view(), name="link-list"),
    path(
        "lists/<str:list_code>/links/<uuid:link_id>/",
        views.LinkDetailView.as_view(),
        name="link-detail",
    ),
]
