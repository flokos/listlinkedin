import threading

import pytest
from django.db import connection

from apps.sharing import services
from apps.sharing.domain import MAX_LINKS_PER_LIST
from apps.sharing.models import SharedLink
from apps.shortener.models import ShortRedirect
from conftest import bearer

pytestmark = pytest.mark.django_db


def links_url(shared_list) -> str:
    return f"/api/v1/lists/{shared_list.public_code}/links/"


def add(api_client, shared_list, token, url="https://example.com/a", title="A"):
    return api_client.post(
        links_url(shared_list),
        {"destination_url": url, "title": title},
        format="json",
        **bearer(token),
    )


def test_owner_can_add_link_with_short_url(api_client, owned_list, settings):
    shared_list, token = owned_list

    response = add(api_client, shared_list, token)

    assert response.status_code == 201
    body = response.json()
    redirect = ShortRedirect.objects.get(link_id=body["id"])
    assert body["destination_url"] == "https://example.com/a"
    assert body["short_url"] == f"{settings.PUBLIC_BASE_URL}/r/{redirect.code}"


def test_link_without_title_is_allowed(api_client, owned_list):
    shared_list, token = owned_list
    response = api_client.post(
        links_url(shared_list),
        {"destination_url": "https://example.com/x"},
        format="json",
        **bearer(token),
    )
    assert response.status_code == 201
    assert response.json()["title"] is None


def test_adding_links_requires_owner_token(api_client, owned_list):
    shared_list, _ = owned_list
    payload = {"destination_url": "https://example.com/a"}

    assert api_client.post(links_url(shared_list), payload, format="json").status_code == 401
    assert add(api_client, shared_list, "wrong").status_code == 403
    assert not SharedLink.objects.exists()


def test_anyone_can_list_links_newest_first_with_pagination(api_client, owned_list):
    shared_list, _ = owned_list
    for i in range(25):
        services.add_link(shared_list, destination_url=f"https://example.com/{i}")

    first_page = api_client.get(links_url(shared_list)).json()
    second_page = api_client.get(links_url(shared_list), {"page": 2}).json()

    assert first_page["count"] == 25
    assert len(first_page["results"]) == 20
    assert first_page["results"][0]["destination_url"] == "https://example.com/24"
    assert all(link["short_url"] for link in first_page["results"])
    returned = [link["id"] for link in first_page["results"] + second_page["results"]]
    assert len(set(returned)) == 25


@pytest.mark.parametrize(
    "url", ["ftp://example.com", "javascript:alert(1)", "not a url", "https://u:p@example.com"]
)
def test_invalid_destinations_are_rejected(api_client, owned_list, url):
    shared_list, token = owned_list
    response = add(api_client, shared_list, token, url=url)
    assert response.status_code == 400
    assert "destination_url" in response.json()


def test_duplicate_destinations_are_rejected_after_normalization(api_client, owned_list):
    shared_list, token = owned_list
    assert add(api_client, shared_list, token, url="https://example.com/a").status_code == 201

    response = add(api_client, shared_list, token, url="  HTTPS://EXAMPLE.com/a ")

    assert response.status_code == 400
    assert SharedLink.objects.count() == 1


def test_same_destination_is_allowed_in_different_lists(api_client, owned_list):
    shared_list, token = owned_list
    other_list, other_token = services.create_list(title="Other")

    assert add(api_client, shared_list, token).status_code == 201
    assert add(api_client, other_list, other_token).status_code == 201


def test_link_limit_is_enforced(api_client, owned_list):
    shared_list, token = owned_list
    for i in range(MAX_LINKS_PER_LIST):
        services.add_link(shared_list, destination_url=f"https://example.com/{i}")

    response = add(api_client, shared_list, token, url="https://example.com/one-too-many")

    assert response.status_code == 400
    assert shared_list.links.count() == MAX_LINKS_PER_LIST


def test_owner_can_edit_link_and_short_code_is_preserved(api_client, owned_list):
    shared_list, token = owned_list
    created = add(api_client, shared_list, token).json()

    response = api_client.patch(
        f"{links_url(shared_list)}{created['id']}/",
        {"destination_url": "https://example.com/new", "title": "New"},
        format="json",
        **bearer(token),
    )

    assert response.status_code == 200
    assert response.json()["destination_url"] == "https://example.com/new"
    assert response.json()["title"] == "New"
    assert response.json()["short_url"] == created["short_url"]
    assert ShortRedirect.objects.filter(link_id=created["id"]).count() == 1


def test_editing_into_a_duplicate_is_rejected(api_client, owned_list):
    shared_list, token = owned_list
    add(api_client, shared_list, token, url="https://example.com/a")
    second = add(api_client, shared_list, token, url="https://example.com/b").json()

    response = api_client.patch(
        f"{links_url(shared_list)}{second['id']}/",
        {"destination_url": "https://example.com/a"},
        format="json",
        **bearer(token),
    )
    assert response.status_code == 400


def test_editing_links_requires_owner_token(api_client, owned_list):
    shared_list, token = owned_list
    link = add(api_client, shared_list, token).json()
    url = f"{links_url(shared_list)}{link['id']}/"

    assert api_client.patch(url, {"title": "x"}, format="json").status_code == 401
    assert api_client.delete(url, **bearer("wrong")).status_code == 403


def test_owner_can_remove_link(api_client, owned_list):
    shared_list, token = owned_list
    link = add(api_client, shared_list, token).json()

    response = api_client.delete(f"{links_url(shared_list)}{link['id']}/", **bearer(token))

    assert response.status_code == 204
    assert not SharedLink.objects.exists()
    assert not ShortRedirect.objects.exists()


def test_links_cannot_be_modified_through_another_list(api_client, owned_list):
    shared_list, token = owned_list
    other_list, other_token = services.create_list(title="Other")
    victim = add(api_client, shared_list, token).json()

    # The attacker owns `other_list` and addresses the victim's link through it.
    url = f"{links_url(other_list)}{victim['id']}/"
    patch = api_client.patch(url, {"title": "pwned"}, format="json", **bearer(other_token))
    delete = api_client.delete(url, **bearer(other_token))

    assert patch.status_code == 404
    assert delete.status_code == 404
    assert SharedLink.objects.get(pk=victim["id"]).title == "A"


@pytest.mark.django_db(transaction=True)
def test_concurrent_adds_never_exceed_link_limit():
    shared_list, _ = services.create_list(title="Race")
    for i in range(MAX_LINKS_PER_LIST - 1):
        services.add_link(shared_list, destination_url=f"https://example.com/{i}")

    results: list[str] = []
    barrier = threading.Barrier(4)

    def add_one(n: int) -> None:
        barrier.wait()
        try:
            services.add_link(shared_list, destination_url=f"https://example.com/race-{n}")
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
    assert shared_list.links.count() == MAX_LINKS_PER_LIST
