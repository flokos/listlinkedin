from django.urls import include, path, re_path
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from apps.shortener.views import ShortRedirectView

# Short codes are Base64URL. A trailing slash is tolerated because some apps add one when
# links are pasted; reverse() builds the canonical slash-less form.
CODE = r"[A-Za-z0-9_-]+"

urlpatterns = [
    path("api/v1/", include("apps.sharing.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # Public list short URL: a temporary redirect to the list's API representation.
    re_path(
        rf"^l/(?P<list_code>{CODE})/?$",
        RedirectView.as_view(pattern_name="list-detail", permanent=False),
        name="list-short-url",
    ),
    re_path(rf"^r/(?P<code>{CODE})/?$", ShortRedirectView.as_view(), name="short-redirect"),
]
