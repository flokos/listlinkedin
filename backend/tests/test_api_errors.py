"""The v2 exception handler: domain errors map to HTTP, v2 bodies carry a `code`."""

import ast
from pathlib import Path

import pytest
from django.conf import settings
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from apps.accounts.authentication import SessionAuthentication
from apps.common import errors
from config.exceptions import exception_handler

factory = APIRequestFactory()


class StalePreview(errors.Conflict):  # a domain error defined by some app
    code = "stale_preview"


def handle(error, path="/api/v2/lists/X/", view=None):
    request = APIView().initialize_request(factory.get(path))
    return exception_handler(error, {"request": request, "view": view or APIView()})


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (errors.NotVisible(), 404, "not_found"),
        (errors.Forbidden(), 403, "permission_denied"),
        (errors.Expired(), 410, "gone"),
        (errors.Conflict(), 409, "conflict"),
        (StalePreview(), 409, "stale_preview"),  # status follows the class hierarchy
        (errors.RevisionMismatch(), 412, "revision_mismatch"),
        (errors.PreconditionRequired(), 428, "precondition_required"),
        (errors.Unprocessable(), 422, "unprocessable"),
    ],
)
def test_domain_errors_map_to_status_and_code(error, status_code, code):
    response = handle(error)

    assert response.status_code == status_code
    assert response.data["code"] == code
    assert response.data["detail"] == error.message


def test_extra_fields_are_added_to_the_body():
    response = handle(StalePreview("The source list changed.", fingerprint="abc"))
    assert response.data == {
        "detail": "The source list changed.",
        "code": "stale_preview",
        "fingerprint": "abc",
    }


def test_authentication_required_is_401_only_with_a_challenge():
    class SessionView(APIView):
        authentication_classes = [SessionAuthentication]

    with_challenge = handle(errors.AuthenticationRequired(), view=SessionView())
    assert with_challenge.status_code == 401
    assert with_challenge["WWW-Authenticate"] == "Session"

    without = handle(errors.AuthenticationRequired(), view=APIView())
    assert without.status_code == 403


def test_v1_paths_get_no_code():
    response = handle(errors.NotVisible(), path="/api/v1/lists/X/")
    assert response.status_code == 404
    assert "code" not in response.data


def test_domain_errors_module_does_not_depend_on_django():
    source = Path(settings.BASE_DIR, "apps", "common", "errors.py").read_text()
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in (node.names if isinstance(node, ast.Import) else [ast.alias(node.module)])
    }
    assert not imported & {"django", "rest_framework"}, imported
