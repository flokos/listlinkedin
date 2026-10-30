"""The API docs page (task 9.1): Swagger UI from this origin, with a CSP that allows nothing
else; every other answer gets the API's strict CSP."""

import pytest
from django.test import Client


@pytest.mark.django_db
def test_the_docs_page_loads_nothing_from_other_sites():
    response = Client().get("/api/docs/")
    html = response.content.decode()
    assert response.status_code == 200
    assert "/api/docs/assets/swagger-ui-bundle.js" in html
    assert "cdn.jsdelivr.net" not in html and "<script>" not in html  # no inline script
    csp = response["Content-Security-Policy"]
    assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp

    script = Client().get("/api/docs/?script=")
    assert script.status_code == 200 and "SwaggerUIBundle" in script.content.decode()


@pytest.mark.django_db
def test_only_swagger_uis_own_files_are_served():
    client = Client()
    bundle = client.get("/api/docs/assets/swagger-ui-bundle.js")
    assert bundle.status_code == 200
    assert bundle["Content-Type"].startswith("text/javascript")
    assert bundle["Cache-Control"] == "public, max-age=86400"
    for name in ("index.html", "..%2Fsettings.py", "swagger-ui.js.map"):
        assert client.get(f"/api/docs/assets/{name}").status_code == 404


@pytest.mark.django_db
def test_api_answers_have_a_csp_that_allows_nothing():
    csp = Client().get("/api/v2/session/")["Content-Security-Policy"]
    assert csp == "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
