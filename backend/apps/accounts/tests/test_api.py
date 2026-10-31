"""Sign-up and sign-in through allauth's headless API, and the /api/v2/ session endpoints."""

import re
from urllib.parse import unquote

import pytest
from django.conf import settings
from django.core import mail
from django.test import Client

from apps.accounts.models import User

AUTH = "/_allauth/browser/v1/auth"
PASSWORD = "correct-horse-battery-staple-42"


@pytest.fixture
def client() -> Client:
    return Client()


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user("ada@example.com", PASSWORD)


def post_json(client: Client, path: str, data: dict, **extra):
    return client.post(path, data, content_type="application/json", **extra)


def session_user(client: Client):
    return client.get("/api/v2/session/").json()["user"]


@pytest.mark.django_db
def test_session_is_anonymous_and_sets_the_csrf_cookie(client):
    response = client.get("/api/v2/session/")

    assert response.status_code == 200
    assert response.json() == {"user": None}
    assert response.cookies[settings.CSRF_COOKIE_NAME].value


@pytest.mark.django_db
def test_sign_up_signs_in_and_sends_a_verification_link_to_the_spa(client):
    response = post_json(
        client, f"{AUTH}/signup", {"email": "Ada@Example.com", "password": PASSWORD}
    )

    assert response.status_code == 200, response.content
    me = session_user(client)
    assert me["email"] == "ada@example.com"
    assert me["email_verified"] is False
    assert len(mail.outbox) == 1

    # The link carries the key in the fragment, percent-encoded, as the SPA reads it.
    key = key_from_link(mail.outbox[0].body, "/verify-email")
    verified = post_json(client, f"{AUTH}/email/verify", {"key": key})
    assert verified.status_code == 200, verified.content
    assert session_user(client)["email_verified"] is True


@pytest.mark.django_db
def test_sign_ups_are_limited_to_ten_an_hour_per_ip():
    """docs/v2/13-SECURITY.md#rate-limits (task 9.1): tighter than allauth's 20 a minute."""
    statuses = [
        post_json(
            Client(), f"{AUTH}/signup", {"email": f"u{n}@example.com", "password": PASSWORD}
        ).status_code
        for n in range(11)
    ]
    assert statuses == [200] * 10 + [429]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("password", "accepted"),
    [
        ("482093715264", True),  # digits only: no composition rules (ASVS V6.2.5)
        ("12345678", False),  # a common password
        ("my listLinkedIn pass", False),  # the site's own name
        ("short1!", False),
        ("x" * 128, True),  # long passphrases are fine
    ],
)
def test_password_rules(password, accepted):
    response = post_json(
        Client(), f"{AUTH}/signup", {"email": "new@example.com", "password": password}
    )
    assert (response.status_code == 200) is accepted, response.content


@pytest.mark.django_db
def test_account_emails_use_our_own_wording(client, user):
    """Task 9.3: allauth's stock emails greeted with "Hello from {host}!"."""
    post_json(client, f"{AUTH}/signup", {"email": "new@example.com", "password": PASSWORD})
    post_json(Client(), f"{AUTH}/password/request", {"email": user.email})
    confirm, reset = mail.outbox
    assert confirm.subject == "[listlinkedin] Confirm your email address"
    assert reset.subject == "[listlinkedin] Your password reset link"
    for message in (confirm, reset):
        assert message.body.startswith("Hi,") and "Hello from" not in message.body
        assert "listlinkedin" in message.body
    assert "/verify-email#key=" in confirm.body and "3 days" in confirm.body
    assert "/reset-password#key=" in reset.body and "one hour" in reset.body


@pytest.mark.django_db
def test_sign_in_and_sign_out(client, user):
    wrong = post_json(client, f"{AUTH}/login", {"email": user.email, "password": "nope-nope"})
    assert wrong.status_code == 400
    assert session_user(client) is None

    right = post_json(client, f"{AUTH}/login", {"email": "ADA@example.com", "password": PASSWORD})
    assert right.status_code == 200, right.content
    assert session_user(client)["id"] == str(user.pk)

    client.delete(f"{AUTH}/session")
    assert session_user(client) is None


@pytest.mark.django_db
def test_password_reset_requests_do_not_reveal_whether_an_account_exists(client, user):
    known = post_json(client, f"{AUTH}/password/request", {"email": user.email})
    unknown = post_json(client, f"{AUTH}/password/request", {"email": "nobody@example.com"})

    assert known.status_code == unknown.status_code == 200
    reset = next(m for m in mail.outbox if user.email in m.to)
    key = key_from_link(reset.body, "/reset-password")
    check = client.get(f"{AUTH}/password/reset", HTTP_X_PASSWORD_RESET_KEY=key)
    assert check.status_code == 200, check.content


def key_from_link(body: str, path: str) -> str:
    """The key from an emailed SPA link like {PUBLIC_BASE_URL}{path}#key=..., decoded."""
    match = re.search(rf"{re.escape(settings.PUBLIC_BASE_URL + path)}#key=(\S+)", body)
    assert match, body
    return unquote(match.group(1))


@pytest.mark.django_db
def test_account_endpoint_requires_sign_in_with_401(client):
    response = client.get("/api/v2/me/")

    assert response.status_code == 401
    assert response["WWW-Authenticate"] == "Session"
    assert response.json()["code"] == "not_authenticated"


@pytest.mark.django_db
def test_users_can_change_their_display_name_but_not_their_email(client, user):
    client.force_login(user)

    response = client.patch(
        "/api/v2/me/",
        {"display_name": "  Ada L.  ", "email": "eve@example.com"},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.pk),
        "email": "ada@example.com",
        "display_name": "Ada L.",
        "email_verified": False,
        "deletion_scheduled_for": None,
    }


@pytest.mark.django_db
def test_invalid_display_name_is_a_400_with_a_code(client, user):
    client.force_login(user)

    response = client.patch(
        "/api/v2/me/", {"display_name": "x" * 81}, content_type="application/json"
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid"
    assert "display_name" in response.json()


@pytest.mark.django_db
def test_signed_in_writes_need_the_csrf_token(user):
    browser = Client(enforce_csrf_checks=True)

    # Signing in is itself CSRF-protected.
    login = {"email": user.email, "password": PASSWORD}
    assert post_json(browser, f"{AUTH}/login", login).status_code == 403
    token = browser.get("/api/v2/session/").cookies[settings.CSRF_COOKIE_NAME].value
    assert post_json(browser, f"{AUTH}/login", login, HTTP_X_CSRFTOKEN=token).status_code == 200

    token = browser.cookies[settings.CSRF_COOKIE_NAME].value  # rotated on sign-in
    patch = {"path": "/api/v2/me/", "data": {"display_name": "Ada"}}
    assert browser.patch(**patch, content_type="application/json").status_code == 403
    assert (
        browser.patch(**patch, content_type="application/json", HTTP_X_CSRFTOKEN=token)
    ).status_code == 200


@pytest.mark.django_db
def test_openapi_marks_v2_account_endpoints_as_session_authenticated(client):
    schema = client.get("/api/schema/", {"format": "json"}).json()

    me = schema["paths"]["/api/v2/me/"]
    assert me["get"]["security"] == me["patch"]["security"] == [{"SessionCookie": []}]
    # The session endpoint also answers signed-out visitors (the empty requirement).
    assert schema["paths"]["/api/v2/session/"]["get"]["security"] == [{"SessionCookie": []}, {}]
    assert schema["components"]["securitySchemes"]["SessionCookie"]["in"] == "cookie"


@pytest.mark.django_db
def test_v1_error_bodies_keep_their_v1_shape(client):
    response = client.get("/api/v1/lists/doesnotexist/")

    assert response.status_code == 404
    assert "code" not in response.json()
