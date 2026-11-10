"""Connected browsers (task 11.1, docs/v2/adr/ADR-020): the browser extension is approved on
this site and exchanges a one-time code, with its PKCE verifier, for a long-lived session
token (the X-Session-Token of ADR-019)."""

import io
import secrets
import threading
from datetime import timedelta
from importlib import import_module

import pytest
from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.sessions.models import Session
from django.core import mail
from django.core.management import call_command
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts import browsers
from apps.accounts.models import ConnectedBrowser, User

PASSWORD = "correct-horse-battery-staple-42"
APPROVALS = "/api/v2/me/browsers/approvals/"
CONNECT = "/api/v2/browsers/connect/"
BROWSERS = "/api/v2/me/browsers/"
ME = "/api/v2/me/"
JSON = {"content_type": "application/json"}
INVALID = {
    "detail": "This code isn't valid any more. Start again from the extension.",
    "code": "invalid_code",
}

SessionStore = import_module(settings.SESSION_ENGINE).SessionStore


@pytest.fixture
def ada(db) -> User:
    user = User.objects.create_user("ada@example.com", PASSWORD)
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    return user


def site(user) -> Client:
    """This site's signed-in page: a cookie session, refused without its CSRF token."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    return client


def csrf(client: Client) -> dict:
    token = client.get("/api/v2/session/").cookies[settings.CSRF_COOKIE_NAME].value
    return {"HTTP_X_CSRFTOKEN": token}


def pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(32)
    return verifier, browsers.challenge_for(verifier)


def approve(client: Client, challenge: str, name: str = "Firefox on Linux"):
    return client.post(APPROVALS, {"challenge": challenge, "name": name}, **JSON, **csrf(client))


def connect(code: str, verifier: str):
    return Client().post(CONNECT, {"code": code, "verifier": verifier}, **JSON)


def connected(user, name: str = "Firefox on Linux") -> dict:
    """The whole flow, as the extension sees its end: `{id, name, session_token, user}`."""
    verifier, challenge = pkce()
    approval = approve(site(user), challenge, name)
    assert approval.status_code == 201, approval.content
    response = connect(approval.json()["code"], verifier)
    assert response.status_code == 201, response.content
    return response.json()


def with_token(token: str) -> dict:
    return {"HTTP_X_SESSION_TOKEN": token}


def me(token: str) -> int:
    return Client().get(ME, **with_token(token)).status_code


def session_of(browser_id) -> Session:
    return Session.objects.get(session_key=ConnectedBrowser.objects.get(pk=browser_id).session_key)


def test_the_challenge_is_pkces_s256():
    """The example in RFC 7636, appendix B."""
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    assert browsers.challenge_for(verifier) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_a_browser_connects_and_acts_as_the_account(ada):
    verifier, challenge = pkce()
    approval = approve(site(ada), challenge)
    assert approval.status_code == 201, approval.content
    assert approval.json()["expires_in"] == 120
    code = approval.json()["code"]
    pending = ConnectedBrowser.objects.get()
    assert pending.session_key is None and pending.code_hash != code  # only the code's hash

    response = connect(code, verifier)

    assert response.status_code == 201, response.content
    assert response["Cache-Control"] == "no-store"
    body = response.json()
    assert body["name"] == "Firefox on Linux" and body["user"]["email"] == ada.email
    token = body["session_token"]
    # The token is a session token (ADR-019): it signs in everywhere, and writes without CSRF.
    extension = Client(enforce_csrf_checks=True)
    assert extension.get(ME, **with_token(token)).json()["email"] == ada.email
    created = extension.post("/api/v2/lists/", {"title": "Saved"}, **JSON, **with_token(token))
    assert created.status_code == 201, created.content

    row = ConnectedBrowser.objects.get()
    assert str(row.pk) == body["id"] and row.code_hash is None and row.challenge == ""
    assert row.connected_at is not None and row.last_used_at is not None
    listed = site(ada).get(BROWSERS).json()
    assert [(b["id"], b["name"], b["current"]) for b in listed] == [
        (body["id"], "Firefox on Linux", False)
    ]
    # Asked by the connected browser itself, the entry is marked as its own.
    assert Client().get(BROWSERS, **with_token(token)).json()[0]["current"] is True


def test_the_account_is_told_by_email_without_any_secret(ada):
    body = connected(ada, "Chrome on Windows")

    assert len(mail.outbox) == 1
    notice = mail.outbox[0]
    assert notice.to == [ada.email]
    assert notice.subject == "[listlinkedin] A browser was connected to your account"
    assert "Chrome on Windows" in notice.body and "/account" in notice.body
    assert body["session_token"] not in notice.body


def test_connecting_stands_when_the_notice_cannot_be_sent(ada, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    settings.EMAIL_HOST, settings.EMAIL_PORT = "127.0.0.1", 9  # nothing listens there

    assert me(connected(ada)["session_token"]) == 200


def test_only_this_sites_own_session_can_approve(ada):
    _, challenge = pkce()
    request = {"path": APPROVALS, "data": {"challenge": challenge, "name": "Firefox"}, **JSON}

    assert Client().post(**request).status_code == 401
    assert site(ada).post(**request).status_code == 403  # a cookie session without CSRF
    # A session token never approves: neither another frontend's (ADR-019) ...
    signed_in = Client().post(
        "/_allauth/app/v1/auth/login", {"email": ada.email, "password": PASSWORD}, **JSON
    )
    app_token = signed_in.json()["meta"]["session_token"]
    assert Client().post(**request, **with_token(app_token)).status_code == 401
    # ... nor a connected browser's, which can do everything else the account can.
    browser_token = connected(ada)["session_token"]
    assert Client().post(**request, **with_token(browser_token)).status_code == 401
    assert ConnectedBrowser.objects.filter(session_key__isnull=True).count() == 0


def test_a_code_works_once_and_only_with_its_verifier(ada):
    verifier, challenge = pkce()
    code = approve(site(ada), challenge).json()["code"]

    wrong = connect(code, pkce()[0])
    assert (wrong.status_code, wrong.json()) == (400, INVALID)
    assert connect(code, verifier).status_code == 201  # a wrong guess doesn't spend the code
    for attempt in (connect(code, verifier), connect(secrets.token_urlsafe(32), verifier)):
        assert (attempt.status_code, attempt.json()) == (400, INVALID)  # used; never issued
    assert ConnectedBrowser.objects.filter(session_key__isnull=False).count() == 1


def test_a_code_expires_after_two_minutes(ada):
    verifier, challenge = pkce()
    code = approve(site(ada), challenge).json()["code"]
    ConnectedBrowser.objects.update(code_expires_at=timezone.now() - timedelta(seconds=1))

    response = connect(code, verifier)

    assert (response.status_code, response.json()) == (400, INVALID)
    # The next approval forgets it.
    assert approve(site(ada), pkce()[1]).status_code == 201
    assert ConnectedBrowser.objects.count() == 1


@pytest.mark.parametrize("how", ["suspended", "deleted"])
def test_an_account_that_can_no_longer_sign_in_cannot_connect(ada, how):
    verifier, challenge = pkce()
    page = site(ada)
    code = approve(page, challenge).json()["code"]

    if how == "suspended":
        call_command("suspend_account", ada.email, "--reason", "phishing", stdout=io.StringIO())
    else:
        deleted = page.delete(ME, {"confirm": ada.email}, **JSON, **csrf(page))
        assert deleted.status_code == 204

    assert connect(code, verifier).status_code == 400
    assert not ConnectedBrowser.objects.exists()


def test_approvals_take_a_challenge_and_a_one_line_name(ada):
    page = site(ada)
    _, challenge = pkce()

    assert approve(page, "too-short").status_code == 400
    assert approve(page, challenge, "  \n ").status_code == 400
    assert approve(page, challenge, "x" * 81).status_code == 400
    assert approve(page, challenge, " Firefox\non \x07  Linux\r\n").status_code == 201
    assert ConnectedBrowser.objects.latest("created_at").name == "Firefox on Linux"
    # The exchange takes a verifier of RFC 7636's shape; anything else isn't looked up.
    bad = Client().post(CONNECT, {"code": "c", "verifier": "short"}, **JSON)
    assert bad.status_code == 400 and "verifier" in bad.json()


def test_disconnecting_ends_the_token_at_once(ada):
    laptop, desktop = connected(ada, "Laptop"), connected(ada, "Desktop")
    keys = list(ConnectedBrowser.objects.values_list("session_key", flat=True))
    page = site(ada)

    assert page.delete(f"{BROWSERS}{laptop['id']}/", **csrf(page)).status_code == 204

    assert me(laptop["session_token"]) == 401
    assert me(desktop["session_token"]) == 200
    assert [b["name"] for b in page.get(BROWSERS).json()] == ["Desktop"]
    assert page.delete(f"{BROWSERS}{laptop['id']}/", **csrf(page)).status_code == 404
    # The extension disconnects itself with its own token.
    own = with_token(desktop["session_token"])
    assert Client().delete(f"{BROWSERS}{desktop['id']}/", **own).status_code == 204
    assert me(desktop["session_token"]) == 401
    assert not ConnectedBrowser.objects.exists()
    assert not Session.objects.filter(session_key__in=keys).exists()


def test_nobody_disconnects_another_accounts_browser(ada):
    eve = User.objects.create_user("eve@example.com", PASSWORD)
    body = connected(ada)
    page = site(eve)

    assert page.delete(f"{BROWSERS}{body['id']}/", **csrf(page)).status_code == 404
    assert page.get(BROWSERS).json() == []
    assert me(body["session_token"]) == 200


def test_a_new_password_ends_connections_like_every_other_session(ada):
    token = connected(ada)["session_token"]
    page = Client()
    assert page.login(email=ada.email, password=PASSWORD)

    changed = page.post(
        "/_allauth/browser/v1/account/password/change",
        {"current_password": PASSWORD, "new_password": PASSWORD + "-2"},
        **JSON,
    )

    assert changed.status_code == 200, changed.content
    assert me(token) == 401
    assert page.get(BROWSERS).json() == []  # the page that changed it stays signed in
    # The row goes with the next approval; nothing lists or revives it meanwhile.
    page = site(User.objects.get(pk=ada.pk))
    assert approve(page, pkce()[1]).status_code == 201
    assert not ConnectedBrowser.objects.filter(session_key__isnull=False).exists()


def test_suspension_ends_connections(ada):
    token = connected(ada)["session_token"]
    key = ConnectedBrowser.objects.get().session_key

    call_command("suspend_account", ada.email, "--reason", "phishing", stdout=io.StringIO())

    assert me(token) == 401
    assert not ConnectedBrowser.objects.exists()
    assert not Session.objects.filter(session_key=key).exists()


def test_deleting_the_account_ends_connections_and_restoring_revives_none(ada):
    token = connected(ada)["session_token"]
    extension = Client()

    # Everything the account can do: the connected browser may even delete the account.
    deleted = extension.delete(ME, {"confirm": ada.email}, **JSON, **with_token(token))

    assert deleted.status_code == 204
    assert me(token) == 401
    assert not ConnectedBrowser.objects.exists()
    page = Client()
    assert page.login(email=ada.email, password=PASSWORD)
    assert page.post("/api/v2/me/restore/").status_code == 200
    assert page.get(BROWSERS).json() == [] and me(token) == 401


def edit_session(browser_id, **mark) -> None:
    """Rewrite the connection's mark in its session, as if time had passed."""
    store = SessionStore(session_key=ConnectedBrowser.objects.get(pk=browser_id).session_key)
    store[browsers.SESSION_MARK] = {**store[browsers.SESSION_MARK], **mark}
    store.save()


def about(moment, expected) -> bool:
    return abs(moment - expected) < timedelta(minutes=1)


def test_using_a_connection_keeps_it_for_ninety_more_days_up_to_a_year(ada):
    body = connected(ada)
    token, now = body["session_token"], timezone.now()
    yesterday = (now - timedelta(days=1)).date().isoformat()
    assert about(session_of(body["id"]).expire_date, now + timedelta(days=90))

    # Used again after 89 idle days: the end moves to 90 days from now, and the day is noted.
    edit_session(body["id"], seen=yesterday)
    Session.objects.update(expire_date=now + timedelta(days=1))
    ConnectedBrowser.objects.update(last_used_at=now - timedelta(days=89))
    assert me(token) == 200
    assert about(session_of(body["id"]).expire_date, now + timedelta(days=90))
    assert about(ConnectedBrowser.objects.get().last_used_at, now)

    # The same day again: nothing is written.
    with CaptureQueriesContext(connection) as queries:
        assert me(token) == 200
    assert not [q["sql"] for q in queries if q["sql"].startswith(("UPDATE", "INSERT", "DELETE"))]

    # Ten days before its latest end, use moves the end no further than that.
    latest = now + timedelta(days=10)
    edit_session(body["id"], seen=yesterday, until=latest.isoformat())
    assert me(token) == 200
    assert about(session_of(body["id"]).expire_date, latest)


def test_an_unused_connection_ends_and_is_no_longer_listed(ada):
    body = connected(ada)

    Session.objects.update(expire_date=timezone.now() - timedelta(seconds=1))

    assert me(body["session_token"]) == 401
    assert site(ada).get(BROWSERS).json() == []


def test_other_session_tokens_are_left_alone(ada):
    """A sign-in through the app client (ADR-019) keeps Django's two weeks: only connected
    browsers are kept alive by use."""
    signed_in = Client().post(
        "/_allauth/app/v1/auth/login", {"email": ada.email, "password": PASSWORD}, **JSON
    )
    token = signed_in.json()["meta"]["session_token"]
    before = Session.objects.get().expire_date

    with CaptureQueriesContext(connection) as queries:
        assert me(token) == 200

    assert Session.objects.get().expire_date == before
    assert not [q["sql"] for q in queries if q["sql"].startswith(("UPDATE", "INSERT", "DELETE"))]
    assert site(ada).get(BROWSERS).json() == []


def test_at_most_ten_browsers_are_connected(ada):
    first = connected(ada)
    for n in range(9):
        connected(ada, f"Browser {n}")
    page = site(ada)

    refused = approve(page, pkce()[1])

    assert refused.status_code == 409 and refused.json()["code"] == "too_many_browsers"
    assert page.delete(f"{BROWSERS}{first['id']}/", **csrf(page)).status_code == 204
    # An approval nobody has used yet holds a place too.
    assert approve(page, pkce()[1]).status_code == 201
    assert approve(page, pkce()[1]).status_code == 409
    assert len(page.get(BROWSERS).json()) == 9


def test_the_exchange_is_rate_limited_per_client(ada, monkeypatch):
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"browser_connect": "2/hour"})
    verifier, _ = pkce()

    statuses = [connect("no-such-code", verifier).status_code for _ in range(3)]

    assert statuses == [400, 400, 429]


@pytest.mark.django_db(transaction=True)
def test_two_exchanges_of_one_code_connect_one_browser():
    user = User.objects.create_user("ada@example.com", PASSWORD)
    verifier, challenge = pkce()
    code = browsers.approve_browser(user, name="Firefox on Linux", challenge=challenge)
    barrier = threading.Barrier(2)
    tokens, refused, errors = [], [], []

    def exchange():
        try:
            barrier.wait()
            tokens.append(browsers.connect_browser(code=code, verifier=verifier)[1])
        except browsers.InvalidCode:
            refused.append(True)
        except Exception as exc:  # noqa: BLE001 - reported below
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=exchange) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert (len(tokens), len(refused)) == (1, 1)
    assert Session.objects.count() == 1
    assert ConnectedBrowser.objects.get().session_key == Session.objects.get().session_key


@pytest.mark.django_db
def test_openapi_says_who_may_call_the_browser_endpoints():
    schema = Client().get("/api/schema/", {"format": "json"}).json()
    paths = schema["paths"]

    # Approving: this site's cookie session only. Connecting: the code is the credential.
    assert paths[APPROVALS]["post"]["security"] == [{"SessionCookie": []}]
    assert paths[CONNECT]["post"].get("security", []) in ([], [{}])
    either = [{"SessionCookie": []}, {"SessionToken": []}]
    assert paths[BROWSERS]["get"]["security"] == either
    assert paths[f"{BROWSERS}{{browser_id}}/"]["delete"]["security"] == either
