"""Deleting an account (docs/v2/adr/ADR-016): DELETE /api/v2/me/ takes effect for everyone at
once, POST /api/v2/me/restore/ undoes it within 30 days, and `purge_deleted_accounts` erases
it afterwards."""

import io
from datetime import timedelta

import pytest
from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from apps.accounts.models import DELETION_GRACE, User
from apps.accounts.services import purge_deleted_accounts
from apps.sharing.models import ListMembership, SharedLink, SharedList
from apps.sharing.selectors import Principal
from apps.sharing.services import lists as list_services
from apps.shortener.models import ShortRedirect

PASSWORD = "correct-horse-battery-staple-42"
ME = "/api/v2/me/"


@pytest.fixture
def ada(db) -> User:
    user = User.objects.create_user("Ada@Example.com", PASSWORD)
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    return user


@pytest.fixture
def bob(db) -> User:
    return User.objects.create_user("bob@example.com", PASSWORD)


def signed_in(user) -> Client:
    client = Client()
    client.force_login(user)
    return client


def delete(client: Client, confirm: str):
    return client.delete(ME, {"confirm": confirm}, content_type="application/json")


def own_list(user, title="Mine") -> SharedList:
    shared_list, _ = list_services.create_list(Principal(user=user), title=title)
    return shared_list


def lists_and_links(ada, bob):
    mine = own_list(ada)
    SharedList.objects.filter(pk=mine.pk).update(visibility="unlisted")  # anyone with the URL
    link = SharedLink.objects.create(
        shared_list=mine, destination_url="https://example.com/", position=0
    )
    ShortRedirect.objects.create(link=link, code="Abc123Abc123Abc1")
    theirs = own_list(bob, "Bob's")
    ListMembership.objects.create(shared_list=theirs, user=ada, role="editor")
    ListMembership.objects.create(shared_list=mine, user=bob, role="viewer")
    return mine, theirs


def test_deleting_hides_everything_at_once_and_signs_out(ada, bob):
    mine, theirs = lists_and_links(ada, bob)
    assert Client().get("/r/Abc123Abc123Abc1").status_code == 302  # before: it resolves
    client = signed_in(ada)

    response = delete(client, "  ada@example.com ")  # case and spaces don't matter

    assert response.status_code == 204
    ada.refresh_from_db()
    assert ada.deletion_scheduled_for == ada.deleted_at + DELETION_GRACE
    # This session is over.
    assert client.get("/api/v2/session/").json()["user"] is None
    assert client.get(ME).status_code == 401
    # For everyone else, Ada's list is gone: unknown to its member and to anonymous readers,
    # and its short URL answers 404.
    bobs = signed_in(bob)
    assert bobs.get(f"/api/v2/lists/{mine.public_code}/").status_code == 404
    assert Client().get(f"/api/v2/lists/{mine.public_code}/").status_code == 404
    assert Client().get("/r/Abc123Abc123Abc1").status_code == 404
    assert [lst["code"] for lst in bobs.get("/api/v2/lists/").json()["results"]] == [
        theirs.public_code
    ]
    # Ada is no longer among the people on Bob's list.
    members = bobs.get(f"/api/v2/lists/{theirs.public_code}/members/").json()["results"]
    assert members == []
    # Nothing is erased yet.
    assert SharedList.objects.filter(pk=mine.pk).exists() and ListMembership.objects.count() == 2


def test_signing_in_during_the_grace_period_offers_restoring(ada, bob):
    mine, theirs = lists_and_links(ada, bob)
    delete(signed_in(ada), ada.email)

    client = Client()
    assert client.login(email=ada.email, password=PASSWORD)  # signing in still works
    session_user = client.get("/api/v2/session/").json()["user"]
    assert session_user["deletion_scheduled_for"] is not None
    # Nothing else answers to this session until the account is restored.
    assert client.get(ME).status_code == 401
    assert client.get(f"/api/v2/lists/{mine.public_code}/").status_code == 404

    restored = client.post("/api/v2/me/restore/")
    assert restored.status_code == 200 and restored.json()["deletion_scheduled_for"] is None
    # Everything is back, and this device stays signed in.
    assert client.get(ME).status_code == 200
    assert client.get(f"/api/v2/lists/{mine.public_code}/").status_code == 200
    assert Client().get("/r/Abc123Abc123Abc1").status_code == 302
    bobs = signed_in(bob)
    members = bobs.get(f"/api/v2/lists/{theirs.public_code}/members/").json()["results"]
    assert [m["user_id"] for m in members] == [str(ada.pk)]


def test_restoring_does_not_revive_old_sessions(ada):
    laptop, phone = signed_in(ada), signed_in(ada)
    delete(laptop, ada.email)
    again = Client()
    again.login(email=ada.email, password=PASSWORD)
    again.post("/api/v2/me/restore/")
    assert phone.get(ME).status_code == 401  # signed out by the deletion, for good


def test_the_grace_period_ends_with_erasure(ada, bob):
    mine, theirs = lists_and_links(ada, bob)
    delete(signed_in(ada), ada.email)
    assert purge_deleted_accounts() == 0  # too early
    User.objects.filter(pk=ada.pk).update(
        deleted_at=timezone.now() - DELETION_GRACE - timedelta(minutes=1)
    )

    out = io.StringIO()
    call_command("purge_deleted_accounts", stdout=out)
    assert "Erased 1" in out.getvalue()

    erased = User.objects.get(pk=ada.pk)  # the row stays, anonymous, for authorship
    assert erased.email == f"deleted-{ada.pk}@deleted.invalid"
    assert (erased.display_name, erased.is_active, erased.has_usable_password()) == (
        "",
        False,
        False,
    )
    assert not EmailAddress.objects.filter(user=erased).exists()
    assert not SharedList.objects.filter(pk=mine.pk).exists()
    assert not SharedLink.objects.exists() and not ShortRedirect.objects.exists()
    assert SharedList.objects.filter(pk=theirs.pk).exists()  # other people's lists stay
    assert not ListMembership.objects.exists()
    assert not Client().login(email=ada.email, password=PASSWORD)
    # The address is free for a new account.
    assert User.objects.create_user("ada@example.com", PASSWORD).pk != ada.pk
    assert purge_deleted_accounts() == 0  # nothing left to erase


def test_the_email_must_be_typed_to_confirm(ada):
    own_list(ada)
    client = signed_in(ada)
    for confirm in ("", "someone@example.com"):
        response = delete(client, confirm)
        assert response.status_code == 400
        assert "confirm" in response.json()
    assert client.delete(ME).status_code == 400  # no body
    ada.refresh_from_db()
    assert ada.deleted_at is None and SharedList.objects.exists()


def test_deleting_needs_a_session(db):
    response = delete(Client(), "ada@example.com")
    assert response.status_code == 401


def test_deleting_needs_the_csrf_token(ada):
    browser = Client(enforce_csrf_checks=True)
    browser.force_login(ada)
    token = browser.get("/api/v2/session/").cookies[settings.CSRF_COOKIE_NAME].value
    assert delete(browser, ada.email).status_code == 403
    ada.refresh_from_db()
    assert ada.deleted_at is None
    response = browser.delete(
        ME, {"confirm": ada.email}, content_type="application/json", HTTP_X_CSRFTOKEN=token
    )
    assert response.status_code == 204


def test_other_sessions_of_a_deleted_account_are_signed_out(ada):
    laptop, phone = signed_in(ada), signed_in(ada)
    assert delete(laptop, ada.email).status_code == 204
    assert phone.get(ME).status_code == 401
    assert phone.get("/api/v2/session/").json()["user"] is None


def test_restoring_needs_a_session_and_is_harmless_when_not_deleted(ada):
    assert Client().post("/api/v2/me/restore/").status_code == 401
    response = signed_in(ada).post("/api/v2/me/restore/")
    assert response.status_code == 200 and response.json()["deletion_scheduled_for"] is None


def test_my_lists_can_be_filtered_by_role(ada, bob):
    mine = own_list(ada)
    theirs = own_list(bob, "Bob's")
    ListMembership.objects.create(shared_list=theirs, user=ada, role="viewer")
    client = signed_in(ada)

    def codes(role):
        response = client.get("/api/v2/lists/", {"role": role})
        assert response.status_code == 200
        return [lst["code"] for lst in response.json()["results"]]

    assert codes("owner") == [mine.public_code]
    assert codes("viewer") == [theirs.public_code]
    assert codes("editor") == []
    assert client.get("/api/v2/lists/", {"role": "admin"}).status_code == 400
