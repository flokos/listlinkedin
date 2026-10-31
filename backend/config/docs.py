"""The API documentation page, /api/docs/ (docs/v2/09-API-DESIGN.md#openapi).

Swagger UI's files come from the drf-spectacular-sidecar package and are served from this
origin, never from a CDN: a script loaded from elsewhere would run with the signed-in user's
cookies (docs/v2/21-SECURITY-REVIEW.md). The page's start-up script is a separate file too
(the split view), so its CSP allows scripts from this origin only.
"""

from pathlib import Path

import drf_spectacular_sidecar
from django.http import FileResponse, Http404
from drf_spectacular.views import SpectacularSwaggerSplitView

ASSETS = (
    Path(drf_spectacular_sidecar.__file__).parent
    / "static"
    / "drf_spectacular_sidecar"
    / "swagger-ui-dist"
)
FILES = {
    "swagger-ui.css": "text/css; charset=utf-8",
    "swagger-ui-bundle.js": "text/javascript; charset=utf-8",
    "swagger-ui-standalone-preset.js": "text/javascript; charset=utf-8",
    "favicon-32x32.png": "image/png",
}
PAGE_CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
    "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)


class DocsView(SpectacularSwaggerSplitView):
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Content-Security-Policy"] = PAGE_CSP
        return response


def docs_asset(request, name: str):
    """One of Swagger UI's files. Only these four names exist."""
    if name not in FILES:
        raise Http404
    response = FileResponse((ASSETS / name).open("rb"), content_type=FILES[name])
    response["Cache-Control"] = "public, max-age=86400"
    return response
