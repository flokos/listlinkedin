"""V1's link tests, kept against /api/v2/ since the legacy path was retired (task 9.6).

The rules are V1's: short URLs on creation, URL validation and normalization, no duplicates,
the 100-link cap (also under concurrency), the short code kept when a URL changes, and links
reachable only through their own list. Who may write is now the owner (or an editor) instead
of the holder of an owner token. V1 listed links newest first; V2 keeps the order people set,
appending new links (docs/v2/adr/ADR-005).
"""

import threading

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.sharing.domain import MAX_LINKS_PER_LIST
from apps.sharing.models import SharedLink
from apps.sharing.selectors import Principal
from apps.sharing.services import links as link_services
from apps.shortener.models import ShortRedirect
from conftest import make_list

pytestmark = pytest.mark.django_db


def links_url(shared_list) -> str:
    return f"/api/v2/lists/{shared_list.public_code}/links/"


def add(client, shared_list, url="https://example.com/a", title="A"):
    return client.post(
        links_url(shared_list), {"destination_url": url, "title": title}, format="json"
    )


def seed(owner, shared_list, count: int, prefix: str = "") -> None:
    for i in range(count):
        link_services.add_link(
            Principal(user=owner),
            shared_list.pk,
            destination_url=f"https://example.com/{prefix}{i}",
        )


def test_owner_can_add_link_with_short_url(owner_client, owned_list, settings):
    response = add(owner_client, owned_list)

    assert response.status_code == 201
    body = response.json()
    redirect = ShortRedirect.objects.get(link_id=body["id"])
    assert body["destination_url"] == "https://example.com/a"
    assert body["short_url"] == f"{settings.PUBLIC_BASE_URL}/r/{redirect.code}"


def test_link_without_title_is_allowed(owner_client, owned_list):
    response = owner_client.post(
        links_url(owned_list), {"destination_url": "https://example.com/x"}, format="json"
    )
    assert response.status_code == 201
    assert response.json()["title"] is None


def test_adding_links_requires_the_owner(api_client, owned_list):
    stranger = APIClient()
    stranger.force_authenticate(User.objects.create_user("eve@example.com", "pw-correct-horse-9"))

    assert add(api_client, owned_list).status_code == 401
    assert add(stranger, owned_list).status_code == 403
    assert not SharedLink.objects.exists()


def test_anyone_can_list_links_in_order_with_pagination(api_client, owner, owned_list):
    seed(owner, owned_list, 25)

    first_page = api_client.get(links_url(owned_list)).json()
    second_page = api_client.get(links_url(owned_list), {"page": 2}).json()

    assert first_page["count"] == 25
    assert len(first_page["results"]) == 20
    assert first_page["results"][0]["destination_url"] == "https://example.com/0"
    assert all(link["short_url"] for link in first_page["results"])
    returned = [link["id"] for link in first_page["results"] + second_page["results"]]
    assert len(set(returned)) == 25


@pytest.mark.parametrize(
    "url", ["ftp://example.com", "javascript:alert(1)", "not a url", "https://u:p@example.com"]
)
def test_invalid_destinations_are_rejected(owner_client, owned_list, url):
    response = add(owner_client, owned_list, url=url)
    assert response.status_code == 400
    assert "destination_url" in response.json()


def test_duplicate_destinations_are_rejected_after_normalization(owner_client, owned_list):
    assert add(owner_client, owned_list, url="https://example.com/a").status_code == 201

    response = add(owner_client, owned_list, url="  HTTPS://EXAMPLE.com/a ")

    assert response.status_code == 400
    assert SharedLink.objects.count() == 1


def test_same_destination_is_allowed_in_different_lists(owner, owner_client, owned_list):
    other_list = make_list(owner, title="Other")

    assert add(owner_client, owned_list).status_code == 201
    assert add(owner_client, other_list).status_code == 201


def test_link_limit_is_enforced(owner, owner_client, owned_list):
    seed(owner, owned_list, MAX_LINKS_PER_LIST)

    response = add(owner_client, owned_list, url="https://example.com/one-too-many")

    assert response.status_code == 400
    assert owned_list.links.filter(deleted_at__isnull=True).count() == MAX_LINKS_PER_LIST


def test_owner_can_edit_link_and_short_code_is_preserved(owner_client, owned_list):
    created = add(owner_client, owned_list).json()

    response = owner_client.patch(
        f"{links_url(owned_list)}{created['id']}/",
        {"destination_url": "https://example.com/new", "title": "New"},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["destination_url"] == "https://example.com/new"
    assert response.json()["title"] == "New"
    assert response.json()["short_url"] == created["short_url"]
    assert ShortRedirect.objects.filter(link_id=created["id"]).count() == 1


def test_editing_into_a_duplicate_is_rejected(owner_client, owned_list):
    add(owner_client, owned_list, url="https://example.com/a")
    second = add(owner_client, owned_list, url="https://example.com/b").json()

    response = owner_client.patch(
        f"{links_url(owned_list)}{second['id']}/",
        {"destination_url": "https://example.com/a"},
        format="json",
    )
    assert response.status_code == 400


def test_editing_links_requires_the_owner(api_client, owner_client, owned_list):
    link = add(owner_client, owned_list).json()
    url = f"{links_url(owned_list)}{link['id']}/"
    stranger = APIClient()
    stranger.force_authenticate(User.objects.create_user("eve@example.com", "pw-correct-horse-9"))

    assert api_client.patch(url, {"title": "x"}, format="json").status_code == 401
    assert stranger.delete(url).status_code == 403


def test_owner_can_remove_link(api_client, owner_client, owned_list):
    link = add(owner_client, owned_list).json()

    response = owner_client.delete(f"{links_url(owned_list)}{link['id']}/")

    assert response.status_code == 204
    # V2 replaces V1's hard delete with a tombstone (docs/v2/adr/ADR-013): the row and its
    # short code stay for history and restore, but the link is gone from the API and its
    # short URL answers 404 (test_shortener). V1's assertion was "no rows left".
    assert api_client.get(links_url(owned_list)).json()["results"] == []
    tombstone = SharedLink.objects.get(pk=link["id"])
    assert tombstone.deleted_at is not None and tombstone.position is None
    assert ShortRedirect.objects.filter(link=tombstone).exists()


def test_links_cannot_be_modified_through_another_list(owner_client, owned_list):
    attacker = User.objects.create_user("eve@example.com", "pw-correct-horse-9")
    other_list = make_list(attacker, title="Other")
    victim = add(owner_client, owned_list).json()
    client = APIClient()
    client.force_authenticate(attacker)

    # The attacker owns `other_list` and addresses the victim's link through it.
    url = f"{links_url(other_list)}{victim['id']}/"
    patch = client.patch(url, {"title": "pwned"}, format="json")
    delete = client.delete(url)

    assert patch.status_code == 404
    assert delete.status_code == 404
    assert SharedLink.objects.get(pk=victim["id"]).title == "A"


@pytest.mark.django_db(transaction=True)
def test_concurrent_adds_never_exceed_link_limit():
    owner = User.objects.create_user("race@example.com", "pw-correct-horse-1")
    shared_list = make_list(owner, title="Race")
    seed(owner, shared_list, MAX_LINKS_PER_LIST - 1)

    results: list[str] = []
    barrier = threading.Barrier(4)

    def add_one(n: int) -> None:
        barrier.wait()
        try:
            link_services.add_link(
                Principal(user=owner),
                shared_list.pk,
                destination_url=f"https://example.com/race-{n}",
            )
            results.append("ok")
        except Exception:
            results.append("rejected")
        finally:
            connection.close()

    threads = [threading.Thread(target=add_one, args=(n,)) for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == ["ok", "rejected", "rejected", "rejected"]
    assert shared_list.links.filter(deleted_at__isnull=True).count() == MAX_LINKS_PER_LIST
