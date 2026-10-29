from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from apps.shortener.views import ShortRedirectView

# Short codes are Base64URL. A trailing slash is tolerated because some apps add one when
# links are pasted; reverse() builds the canonical slash-less form.
CODE = r"[A-Za-z0-9_-]+"

api_v2 = [
    path("", include("apps.accounts.urls")),
    path("", include("apps.sharing.v2.urls")),
]

urlpatterns = [
    path("api/v1/", include("apps.sharing.urls")),
    path("api/v2/", include(api_v2)),
    # Sign-up, sign-in, email verification, password reset: django-allauth's headless API.
    path("_allauth/", include("allauth.headless.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # Public list short URL: a temporary redirect to the list's API representation. The
    # canonical URL may carry a cosmetic slug (/l/{code}/{slug}), which is ignored.
    re_path(
        rf"^l/(?P<list_code>{CODE})(?:/[^/]+)?/?$",
        RedirectView.as_view(pattern_name="list-detail", permanent=False),
        name="list-short-url",
    ),
    re_path(rf"^r/(?P<code>{CODE})/?$", ShortRedirectView.as_view(), name="short-redirect"),
]

# Development only (a no-op unless DEBUG): in production nginx serves /media/ itself.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
