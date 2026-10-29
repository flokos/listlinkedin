"""DELETE /api/v2/me/: deleting an account and the lists it owns (docs/v2/09-API-DESIGN.md)."""

import pytest
from allauth.account.models import EmailAddress
from django.conf import settings
from django.test import Client

from apps.accounts.models import User
from apps.sharing import services as legacy_services
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


def test_deleting_an_account_deletes_its_lists_and_signs_out(ada, bob):
    mine = own_list(ada)
    link = SharedLink.objects.create(
        shared_list=mine, destination_url="https://example.com/", position=0
    )
    ShortRedirect.objects.create(link=link, code="Abc123Abc123Abc1")
    theirs = own_list(bob, "Bob's")
    ListMembership.objects.create(shared_list=theirs, user=ada, role="editor")
    ListMembership.objects.create(shared_list=mine, user=bob, role="viewer")
    client = signed_in(ada)

    response = delete(client, "  ada@example.com ")  # case and spaces don't matter

    assert response.status_code == 204
    assert not User.objects.filter(pk=ada.pk).exists()
    assert not SharedList.objects.filter(pk=mine.pk).exists()
    assert not SharedLink.objects.exists() and not ShortRedirect.objects.exists()
    assert not EmailAddress.objects.filter(email__iexact="ada@example.com").exists()
    # Other people's lists stay; only the membership goes.
    assert SharedList.objects.filter(pk=theirs.pk).exists()
    assert list(ListMembership.objects.all()) == []
    # This session is over.
    assert client.get("/api/v2/session/").json()["user"] is None
    assert client.get(ME).status_code == 401


def test_the_email_must_be_typed_to_confirm(ada):
    own_list(ada)
    client = signed_in(ada)
    for confirm in ("", "someone@example.com"):
        response = delete(client, confirm)
        assert response.status_code == 400
        assert "confirm" in response.json()
    assert client.delete(ME).status_code == 400  # no body
    assert User.objects.filter(pk=ada.pk).exists() and SharedList.objects.exists()


def test_deleting_needs_a_session(db):
    response = delete(Client(), "ada@example.com")
    assert response.status_code == 401


def test_deleting_needs_the_csrf_token(ada):
    browser = Client(enforce_csrf_checks=True)
    browser.force_login(ada)
    token = browser.get("/api/v2/session/").cookies[settings.CSRF_COOKIE_NAME].value
    assert delete(browser, ada.email).status_code == 403
    assert User.objects.filter(pk=ada.pk).exists()
    response = browser.delete(
        ME, {"confirm": ada.email}, content_type="application/json", HTTP_X_CSRFTOKEN=token
    )
    assert response.status_code == 204


def test_other_sessions_of_a_deleted_account_are_signed_out(ada):
    laptop, phone = signed_in(ada), signed_in(ada)
    assert delete(laptop, ada.email).status_code == 204
    assert phone.get(ME).status_code == 401


def test_legacy_lists_claimed_by_nobody_are_untouched(ada):
    legacy, _ = legacy_services.create_list(title="Edit-link list")
    assert delete(signed_in(ada), ada.email).status_code == 204
    assert SharedList.objects.filter(pk=legacy.pk).exists()


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
