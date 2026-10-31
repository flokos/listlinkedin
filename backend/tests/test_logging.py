"""Logging (task 9.1, docs/v2/14-INFRASTRUCTURE.md#health-checks-and-observability and
docs/v2/13-SECURITY.md#logging-and-secrets): request ids, the JSON format, and what logs never
contain."""

import json
import logging
import re
from urllib.parse import unquote

import pytest
from allauth.account.models import EmailAddress
from django.core import mail
from django.test import Client

from apps.accounts.models import User
from apps.sharing.services import legacy as legacy_services
from config.logging import (
    REQUEST_ID,
    USER_ID,
    JsonFormatter,
    RequestIdFilter,
    request_id_from,
)

PASSWORD = "correct-horse-battery-staple-42"
AUTH = "/_allauth/browser/v1/auth"


def test_requests_get_nginxs_id_or_a_new_one(db):
    client = Client()
    given = client.get("/api/v2/session/", HTTP_X_REQUEST_ID="0123456789abcdef0123456789abcdef")
    assert given["X-Request-ID"] == "0123456789abcdef0123456789abcdef"
    made = client.get("/api/v2/session/")["X-Request-ID"]
    assert re.fullmatch(r"[0-9a-f]{32}", made)
    # Anything that could forge log lines is replaced.
    forged = client.get("/api/v2/session/", HTTP_X_REQUEST_ID="x\nERROR fake line")
    assert re.fullmatch(r"[0-9a-f]{32}", forged["X-Request-ID"])
    assert REQUEST_ID.get() == "-"  # nothing leaks into the next request
    assert request_id_from("short") != "short"


def record(message="Hello %s", args=("world",), exc_info=None) -> logging.LogRecord:
    rec = logging.LogRecord("apps.test", logging.ERROR, __file__, 1, message, args, exc_info)
    RequestIdFilter().filter(rec)
    return rec


def test_json_lines_carry_the_request_id_and_the_traceback():
    token, who = REQUEST_ID.set("abcdef0123456789"), USER_ID.set("user-1")
    try:
        plain = json.loads(JsonFormatter().format(record()))
    finally:
        REQUEST_ID.reset(token)
        USER_ID.reset(who)
    assert plain["message"] == "Hello world" and plain["level"] == "ERROR"
    assert plain["logger"] == "apps.test" and plain["request_id"] == "abcdef0123456789"
    assert plain["user_id"] == "user-1"
    assert plain["time"].endswith("+00:00")
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        failed = json.loads(JsonFormatter().format(record(exc_info=sys.exc_info())))
    assert failed["request_id"] == "-" and "ValueError: boom" in failed["exception"]


def test_production_logs_json(monkeypatch):
    import importlib

    import config.settings.production as production

    monkeypatch.setenv("DJANGO_SECRET_KEY", "x" * 50)
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "go.example.test")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://go.example.test")
    reloaded = importlib.reload(production)
    assert reloaded.LOGGING["handlers"]["console"]["formatter"] == "json"
    assert reloaded.LOGGING["handlers"]["console"]["filters"] == ["request_id"]


@pytest.mark.django_db
def test_sign_ins_and_account_changes_are_logged_by_user_id(caplog):
    caplog.set_level(logging.INFO, logger="apps.accounts.auth")
    user = User.objects.create_user("ada@example.com", PASSWORD)
    client = Client()
    json_post = {"content_type": "application/json"}
    client.post(f"{AUTH}/login", {"email": "ada@example.com", "password": "nope"}, **json_post)
    client.post(f"{AUTH}/login", {"email": "ada@example.com", "password": PASSWORD}, **json_post)
    client.delete(f"{AUTH}/session")
    messages = [r.getMessage() for r in caplog.records if r.name == "apps.accounts.auth"]
    assert messages == [
        "Sign-in failed",
        f"Signed in: user {user.pk}",
        f"Signed out: user {user.pk}",
    ]


@pytest.mark.django_db
def test_api_answers_are_never_stored_by_browsers():
    client = Client()
    assert client.get("/api/v2/session/")["Cache-Control"] == "no-store"
    assert client.get("/api/v2/directory/lists/")["Cache-Control"] == "no-store"


def key_from(body: str, path: str) -> str:
    return unquote(re.search(rf"{path}#key=(\S+)", body).group(1))


@pytest.mark.django_db
def test_secrets_and_addresses_never_reach_the_logs(caplog, settings):
    """Session ids, CSRF tokens, verification and reset keys, edit-link tokens and email
    addresses: none is ever logged, on success or failure (extends V1's token test)."""
    settings.MODERATION_EMAIL = "moderation@example.test"
    caplog.set_level(logging.DEBUG)
    client = Client()
    json_post = {"content_type": "application/json"}

    client.post(f"{AUTH}/signup", {"email": "ada@example.com", "password": PASSWORD}, **json_post)
    verify_key = key_from(mail.outbox[-1].body, "/verify-email")
    client.post(f"{AUTH}/email/verify", {"key": verify_key}, **json_post)
    client.post(f"{AUTH}/email/verify", {"key": verify_key + "x"}, **json_post)  # a failure
    session_id = client.cookies["sessionid"].value
    csrf = client.get("/api/v2/session/").cookies.get("csrftoken")
    csrf_value = csrf.value if csrf else client.cookies["csrftoken"].value

    # Claiming a legacy list with its edit link, and a wrong one.
    legacy, owner_token = legacy_services.create_list(title="Old list")
    bearer = {"HTTP_AUTHORIZATION": f"Bearer {owner_token}"}
    client.post(f"/api/v2/lists/{legacy.public_code}/claim/", **bearer)
    client.post(f"/api/v2/lists/{legacy.public_code}/claim/", HTTP_AUTHORIZATION="Bearer nope")

    # Adding people by email (an unknown address too), then a password reset.
    User.objects.filter(email="ada@example.com").update(display_name="Ada")
    bob = User.objects.create_user("bob@example.com", PASSWORD)
    EmailAddress.objects.create(user=bob, email=bob.email, verified=True, primary=True)
    for email in ("bob@example.com", "nobody@example.com"):
        client.post(
            f"/api/v2/lists/{legacy.public_code}/members/",
            {"email": email, "role": "viewer"},
            **json_post,
        )
    client.post(f"{AUTH}/password/request", {"email": "ada@example.com"}, **json_post)
    reset_key = key_from(mail.outbox[-1].body, "/reset-password")
    Client().post(
        f"{AUTH}/password/reset", {"key": reset_key, "password": PASSWORD + "!"}, **json_post
    )
    Client().post(f"{AUTH}/login", {"email": "bob@example.com", "password": "wrong"}, **json_post)

    assert len(caplog.records) > 5  # these requests were logged
    for secret in (session_id, csrf_value, verify_key, reset_key, owner_token):
        assert secret not in caplog.text
    for address in ("ada@example.com", "bob@example.com", "nobody@example.com"):
        assert address not in caplog.text
