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
    # Connected browsers (ADR-020): approve on this site, connect from the extension.
    path(
        "me/browsers/", views.ConnectedBrowserViewSet.as_view({"get": "list"}), name="me-browsers"
    ),
    path(
        "me/browsers/approvals/",
        views.BrowserApprovalViewSet.as_view({"post": "create"}),
        name="me-browser-approvals",
    ),
    path(
        "me/browsers/<uuid:browser_id>/",
        views.ConnectedBrowserViewSet.as_view({"delete": "destroy"}),
        name="me-browser",
    ),
    path(
        "browsers/connect/",
        views.BrowserConnectViewSet.as_view({"post": "create"}),
        name="browser-connect",
    ),
]
