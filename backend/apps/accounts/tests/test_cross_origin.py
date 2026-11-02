"""Frontends on other domains (ADR-019): CORS for the origins in CORS_ALLOWED_ORIGINS, and
sign-in through allauth's `app` client with a session token in X-Session-Token."""

import io

import pytest
from allauth.account.models import EmailAddress
from django.core.management import call_command
from django.test import Client, override_settings

from apps.accounts.models import User
from tests.test_settings import run_check

APP_AUTH = "/_allauth/app/v1/auth"
PASSWORD = "correct-horse-battery-staple-42"
ORIGIN = "https://app.example.org"
ME = "/api/v2/me/"


@pytest.fixture(autouse=True)
def allowed_origin(settings):
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]


@pytest.fixture
def ada(db) -> User:
    user = User.objects.create_user("ada@example.com", PASSWORD)
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    return user


def browser() -> Client:
    """A client that, like a browser, fails any request without a valid CSRF token when it
    carries a session cookie."""
    return Client(enforce_csrf_checks=True)


def sign_in(email: str = "ada@example.com") -> str:
    response = browser().post(
        f"{APP_AUTH}/login",
        {"email": email, "password": PASSWORD},
        content_type="application/json",
        HTTP_ORIGIN=ORIGIN,
    )
    assert response.status_code == 200, response.content
    assert response["Access-Control-Allow-Origin"] == ORIGIN
    return response.json()["meta"]["session_token"]


def with_token(token: str) -> dict:
    return {"HTTP_X_SESSION_TOKEN": token, "HTTP_ORIGIN": ORIGIN}


def preflight(path: str, origin: str = ORIGIN):
    return Client().options(
        path,
        HTTP_ORIGIN=origin,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type, x-session-token",
    )


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/api/v2/lists/", f"{APP_AUTH}/login"])
def test_the_api_and_the_app_client_answer_allowed_origins_without_credentials(path):
    response = preflight(path)

    assert response.status_code == 200
    assert response["Access-Control-Allow-Origin"] == ORIGIN
    assert "x-session-token" in response["Access-Control-Allow-Headers"]
    # Browsers never send this site's cookies cross-origin, so cookie sessions and their
    # CSRF protection stay first-party.
    assert not response.has_header("Access-Control-Allow-Credentials")


@pytest.mark.django_db
def test_other_origins_get_no_cors_headers():
    assert not preflight("/api/v2/lists/", "https://evil.example").has_header(
        "Access-Control-Allow-Origin"
    )
    with override_settings(CORS_ALLOWED_ORIGINS=[]):  # the default: no CORS at all
        assert not preflight("/api/v2/lists/").has_header("Access-Control-Allow-Origin")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path", ["/_allauth/browser/v1/auth/login", "/r/Abc123Abc123Abc1", "/api/docs/"]
)
def test_cookie_endpoints_short_urls_and_docs_stay_same_origin(path):
    response = Client().get(path, HTTP_ORIGIN=ORIGIN)
    assert not response.has_header("Access-Control-Allow-Origin")


def test_the_session_token_signs_in_without_cookies_or_csrf(ada):
    token = sign_in()

    me = browser().get(ME, **with_token(token))
    assert me.status_code == 200 and me.json()["email"] == ada.email
    assert me["Access-Control-Allow-Origin"] == ORIGIN
    # Writes need no CSRF token: browsers never add the header by themselves.
    created = browser().post(
        "/api/v2/lists/", {"title": "Mine"}, content_type="application/json", **with_token(token)
    )
    assert created.status_code == 201, created.content
    assert browser().get(ME, HTTP_X_SESSION_TOKEN="not-a-token").status_code == 401


def test_signing_out_ends_the_token(ada):
    token = sign_in()

    assert browser().delete(f"{APP_AUTH}/session", **with_token(token)).status_code == 401
    assert browser().get(ME, **with_token(token)).status_code == 401


def test_suspension_ends_the_token(ada):
    token = sign_in()

    call_command("suspend_account", ada.email, "--reason", "phishing", stdout=io.StringIO())

    assert browser().get(ME, **with_token(token)).status_code == 401


def test_a_deleted_account_signs_in_only_to_restore(ada):
    token = sign_in()
    deleted = browser().delete(
        ME, {"confirm": ada.email}, content_type="application/json", **with_token(token)
    )
    assert deleted.status_code == 204
    assert browser().get(ME, **with_token(token)).status_code == 401  # this device is out

    token = sign_in()  # signing in during the grace period still works (ADR-016)
    session = browser().get("/api/v2/session/", **with_token(token)).json()
    assert session["user"]["deletion_scheduled_for"] is not None
    assert browser().get(ME, **with_token(token)).status_code == 401

    restored = browser().post("/api/v2/me/restore/", **with_token(token))
    assert restored.status_code == 200, restored.content
    assert browser().get(ME, **with_token(token)).status_code == 200


@pytest.mark.parametrize(
    "value",
    [
        "*",
        "https://*.example.org",
        "http://app.example.org",  # plain http is for local development only
        "https://app.example.org/app",
        "app.example.org",
    ],
)
def test_malformed_cors_origins_refuse_to_start(value):
    result = run_check(CORS_ALLOWED_ORIGINS=value)
    assert result.returncode != 0
    assert "CORS_ALLOWED_ORIGINS" in result.stderr


def test_cors_origins_accept_https_and_local_development():
    result = run_check(CORS_ALLOWED_ORIGINS="https://app.example.org, http://localhost:5174")
    assert result.returncode == 0, result.stderr
