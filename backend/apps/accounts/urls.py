from django.urls import path

from . import views

# Singleton resources, so explicit routes onto the ViewSets instead of a router.
urlpatterns = [
    path("session/", views.SessionViewSet.as_view({"get": "retrieve"}), name="session"),
    path(
        "me/",
        views.MeViewSet.as_view(
            {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
        ),
        name="me",
    ),
    path("me/restore/", views.RestoreViewSet.as_view({"post": "create"}), name="me-restore"),
]
