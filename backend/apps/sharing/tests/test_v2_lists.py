"""/api/v2/lists/ with accounts and visibility, and visibility on /r/."""

import uuid
from datetime import timedelta

import pytest
from allauth.account.models import EmailAddress
from django.db import IntegrityError
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.sharing.models import ListMembership, SharedLink, SharedList

URL = "/api/v2/lists/"


@pytest.fixture
def alice(db):
    return User.objects.create_user("alice@example.com", "pw-correct-horse-1")


@pytest.fixture
def bob(db):
    return User.objects.create_user("bob@example.com", "pw-correct-horse-2")


def client_for(user=None) -> APIClient:
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return client


def create(user, **data):
    response = client_for(user).post(URL, {"title": "Dev tools", **data}, format="json")
    assert response.status_code == 201, response.content
    return response.json()


def add_member(user, code, role):
    ListMembership.objects.create(
        shared_list=SharedList.objects.get(public_code=code), user=user, role=role
    )


def test_creating_needs_an_account(db):
    response = client_for().post(URL, {"title": "x"}, format="json")
    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_new_lists_are_private_permanent_and_owned(alice):
    data = create(alice, description="Things we use")

    assert data["visibility"] == "private"
    assert data["expires_at"] is None
    assert data["my_role"] == "owner"
    assert data["legacy"] is False
    assert data["slug"] == "dev-tools"
    assert data["url"].endswith(f"/l/{data['code']}/dev-tools")
    assert {"edit", "settings", "delete", "members"} <= set(data["permissions"])
    assert SharedList.objects.get(public_code=data["code"]).owner == alice


def test_idempotency_key_returns_the_first_list(alice, bob):
    key = str(uuid.uuid4())
    first = client_for(alice).post(URL, {"title": "A"}, format="json", HTTP_IDEMPOTENCY_KEY=key)
    again = client_for(alice).post(URL, {"title": "A"}, format="json", HTTP_IDEMPOTENCY_KEY=key)
    other = client_for(bob).post(URL, {"title": "A"}, format="json", HTTP_IDEMPOTENCY_KEY=key)

    assert first.status_code == 201
    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]
    assert other.status_code == 409
    assert other.json()["code"] == "idempotency_key_reused"
    assert SharedList.objects.count() == 1

    bad = client_for(alice).post(URL, {"title": "A"}, format="json", HTTP_IDEMPOTENCY_KEY="x")
    assert bad.status_code == 400


def test_public_lists_need_a_verified_email(alice):
    response = client_for(alice).post(URL, {"title": "A", "visibility": "public"}, format="json")
    assert response.status_code == 400
    assert "visibility" in response.json()

    EmailAddress.objects.create(user=alice, email=alice.email, verified=True, primary=True)
    assert create(alice, visibility="public")["visibility"] == "public"


@pytest.mark.parametrize(
    ("visibility", "anonymous", "stranger"),
    [("private", 404, 404), ("unlisted", 200, 200), ("public", 200, 200)],
)
def test_who_can_view(alice, bob, visibility, anonymous, stranger):
    EmailAddress.objects.create(user=alice, email=alice.email, verified=True, primary=True)
    code = create(alice, visibility=visibility)["code"]

    assert client_for().get(f"{URL}{code}/").status_code == anonymous
    assert client_for(bob).get(f"{URL}{code}/").status_code == stranger
    add_member(bob, code, "viewer")
    assert client_for(bob).get(f"{URL}{code}/").status_code == 200


def test_private_lists_look_exactly_like_unknown_ones(alice):
    code = create(alice)["code"]
    hidden = client_for().get(f"{URL}{code}/")
    unknown = client_for().get(f"{URL}NoSuchListCode00/")
    assert hidden.status_code == unknown.status_code == 404
    assert hidden.json() == unknown.json()


def test_owner_is_shown_on_public_lists_and_to_members_only(alice, bob):
    alice.display_name = "Alice"
    alice.save()
    code = create(alice, visibility="unlisted")["code"]
    assert client_for().get(f"{URL}{code}/").json()["owner"] is None
    add_member(bob, code, "viewer")
    assert client_for(bob).get(f"{URL}{code}/").json()["owner"] == {"display_name": "Alice"}


def test_editors_change_content_owners_change_settings(alice, bob):
    code = create(alice)["code"]
    add_member(bob, code, "editor")
    editor = client_for(bob)

    renamed = editor.patch(f"{URL}{code}/", {"title": "Better name"}, format="json")
    assert renamed.status_code == 200
    assert renamed.json()["slug"] == "better-name"
    settings = editor.patch(f"{URL}{code}/", {"visibility": "unlisted"}, format="json")
    assert settings.status_code == 403
    assert editor.delete(f"{URL}{code}/").status_code == 403

    owner = client_for(alice)
    changed = owner.patch(
        f"{URL}{code}/", {"visibility": "unlisted", "allow_fork": True}, format="json"
    )
    assert changed.json()["visibility"] == "unlisted"
    assert changed.json()["allow_fork"] is True
    assert owner.delete(f"{URL}{code}/").status_code == 204


def test_viewers_cannot_edit(alice, bob):
    code = create(alice)["code"]
    add_member(bob, code, "viewer")
    response = client_for(bob).patch(f"{URL}{code}/", {"title": "x"}, format="json")
    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


def test_expiry_must_be_in_the_future_and_expired_lists_are_gone(alice):
    past = (timezone.now() - timedelta(hours=1)).isoformat()
    response = client_for(alice).post(URL, {"title": "x", "expires_at": past}, format="json")
    assert response.status_code == 400

    code = create(alice)["code"]
    SharedList.objects.filter(public_code=code).update(expires_at=timezone.now())
    assert client_for(alice).get(f"{URL}{code}/").status_code == 410


def test_my_lists_shows_owned_and_shared_lists_only(alice, bob):
    mine = create(alice, title="Mine")["code"]
    shared = create(bob, title="Shared with Alice")["code"]
    create(bob, title="Bob's unlisted", visibility="unlisted")
    add_member(alice, shared, "editor")

    response = client_for(alice).get(URL)

    assert response.status_code == 200
    rows = {row["code"]: row for row in response.json()["results"]}
    assert set(rows) == {mine, shared}
    assert rows[mine]["my_role"] == "owner"
    assert rows[shared]["my_role"] == "editor"
    assert client_for().get(URL).status_code == 401


# Database invariants (L2: since 9.6 the owner is required)


@pytest.mark.django_db
def test_every_list_has_a_manager():
    with pytest.raises(IntegrityError):
        SharedList.objects.create(public_code="NoManager0000000", title="x")


# Visibility on reads and short URLs


def test_anonymous_readers_never_see_private_lists(alice):
    """Was V1's API check; /api/v1/ is gone (9.6), and v2 hides private lists the same way."""
    code = create(alice)["code"]
    assert client_for().get(f"{URL}{code}/").status_code == 404
    assert client_for().get(f"{URL}{code}/links/").status_code == 404

    unlisted = create(alice, visibility="unlisted")["code"]
    data = client_for().get(f"{URL}{unlisted}/").json()
    assert data["expires_at"] is None
    assert data["legacy"] is False


def test_short_urls_respect_the_lists_visibility(alice, bob):
    code = create(alice)["code"]
    shared_list = SharedList.objects.get(public_code=code)
    link = SharedLink.objects.create(
        shared_list=shared_list, destination_url="https://example.com/", position=0
    )
    from apps.shortener.services import create_redirect

    short = create_redirect(link).code

    assert client_for().get(f"/r/{short}").status_code == 404
    assert client_for(bob).get(f"/r/{short}").status_code == 404
    add_member(bob, code, "viewer")
    member = APIClient()
    member.force_login(bob)
    response = member.get(f"/r/{short}")
    assert response.status_code == 302
    assert response["Location"] == "https://example.com/"


# Links on /api/v2/ (pulled forward from task 2.1)


def test_editors_manage_links_of_account_lists(alice, bob):
    code = create(alice)["code"]
    add_member(bob, code, "editor")
    links = f"{URL}{code}/links/"

    added = client_for(bob).post(
        links, {"destination_url": "https://example.com/a", "title": "A"}, format="json"
    )
    assert added.status_code == 201, added.content
    link = added.json()
    assert link["short_url"]
    edited = client_for(alice).patch(
        f"{links}{link['id']}/", {"destination_url": "https://example.com/b"}, format="json"
    )
    assert edited.json()["short_url"] == link["short_url"]  # K1
    assert client_for(alice).get(links).json()["count"] == 1
    assert client_for(bob).delete(f"{links}{link['id']}/").status_code == 204


def test_viewers_and_strangers_cannot_change_links(alice, bob):
    code = create(alice, visibility="unlisted")["code"]
    add_member(bob, code, "viewer")
    body = {"destination_url": "https://example.com/"}
    assert client_for(bob).post(f"{URL}{code}/links/", body, format="json").status_code == 403
    assert client_for().post(f"{URL}{code}/links/", body, format="json").status_code == 401
    assert client_for().get(f"{URL}{code}/links/").status_code == 200  # unlisted: readable


def test_private_list_links_are_hidden(alice):
    code = create(alice)["code"]
    assert client_for().get(f"{URL}{code}/links/").status_code == 404
