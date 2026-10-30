"""Discovery (task 8.1, docs/v2/09-API-DESIGN.md#directory): tags, the directories of lists
and groups, tag facets, and that nothing but public resources ever shows."""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import User
from apps.groups import services as group_services
from apps.groups.models import Group, GroupList
from apps.sharing.domain import normalize_tags
from apps.sharing.models import ListMembership, SharedLink, SharedList
from apps.sharing.policy import Visibility
from apps.sharing.selectors import Principal
from apps.sharing.services import links as link_services
from apps.sharing.services import lists as list_services
from apps.versioning.models import ListRevision

URL = "/api/v2/"


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


def make_list(owner, title, visibility=Visibility.PUBLIC, description="", tags=()):
    shared_list = list_services.create_list(
        Principal(user=owner), title=title, description=description
    )[0]
    SharedList.objects.filter(pk=shared_list.pk).update(
        visibility=visibility.value, tags=list(tags)
    )
    shared_list.refresh_from_db()
    return shared_list


def make_group(owner, title, visibility=Visibility.PUBLIC, tags=(), lists=()):
    group = group_services.create_group(Principal(user=owner), title=title)
    Group.objects.filter(pk=group.pk).update(visibility=visibility.value, tags=list(tags))
    for position, shared_list in enumerate(lists):
        GroupList.objects.create(group=group, shared_list=shared_list, position=position)
    return group


def titles(response) -> list[str]:
    assert response.status_code == 200, response.content
    return [item["title"] for item in response.json()["results"]]


def directory(kind="lists", user=None, **params):
    return client_for(user).get(f"{URL}directory/{kind}/", params)


# Tags.


def test_tags_are_normalized():
    assert normalize_tags([" Dev ", "web_dev", "dev", "", "AI  Tools"]) == [
        "dev",
        "web-dev",
        "ai-tools",
    ]
    for bad in (["c++"], ["x" * 33], ["-dev"], ["a--b"]):
        with pytest.raises(ValidationError):
            normalize_tags(bad)
    with pytest.raises(ValidationError, match="At most 10"):
        normalize_tags([f"t{i}" for i in range(11)])


def test_owners_and_editors_set_tags_without_a_revision(alice, bob):
    shared_list = make_list(alice, "Tools", Visibility.PRIVATE)
    url = f"{URL}lists/{shared_list.public_code}/"
    revisions = ListRevision.objects.filter(shared_list=shared_list).count()

    response = client_for(alice).patch(url, {"tags": ["Dev", "web_dev", "dev"]}, format="json")
    assert response.status_code == 200, response.content
    assert response.json()["tags"] == ["dev", "web-dev"]
    assert "tags" in response.json()["permissions"]
    assert ListRevision.objects.filter(shared_list=shared_list).count() == revisions

    ListMembership.objects.create(shared_list=shared_list, user=bob, role="viewer")
    assert client_for(bob).patch(url, {"tags": ["x"]}, format="json").status_code == 403
    ListMembership.objects.filter(user=bob).update(role="editor")
    assert client_for(bob).patch(url, {"tags": ["x"]}, format="json").status_code == 200

    bad = client_for(alice).patch(url, {"tags": ["not ok!"]}, format="json")
    assert bad.status_code == 400 and "tags" in bad.json()
    too_many = client_for(alice).patch(url, {"tags": [f"t{i}" for i in range(11)]}, format="json")
    assert too_many.status_code == 400


def test_lists_and_groups_are_created_with_tags(alice):
    """Tags are accepted on creation too (a 500 before task 8.2's e2e test found it)."""
    client = client_for(alice)
    created = client.post(f"{URL}lists/", {"title": "Tools", "tags": ["Dev Tools"]}, format="json")
    assert created.status_code == 201, created.content
    assert created.json()["tags"] == ["dev-tools"]
    group = client.post(f"{URL}groups/", {"title": "Portal", "tags": ["ops", "OPS"]}, format="json")
    assert group.status_code == 201, group.content
    assert group.json()["tags"] == ["ops"]
    bad = client.post(f"{URL}groups/", {"title": "x", "tags": ["no!"]}, format="json")
    assert bad.status_code == 400


def test_an_edit_link_cant_set_tags(owned_list):
    legacy, token = owned_list
    response = APIClient().patch(
        f"{URL}lists/{legacy.public_code}/",
        {"tags": ["dev"]},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert response.status_code == 403


def test_group_editors_set_tags(alice, bob):
    group = make_group(alice, "Portal", Visibility.PRIVATE)
    url = f"{URL}groups/{group.code}/"
    response = client_for(alice).patch(url, {"tags": ["Dev"]}, format="json")
    assert response.status_code == 200 and response.json()["tags"] == ["dev"]
    from apps.groups.models import GroupMembership

    GroupMembership.objects.create(group=group, user=bob, role="viewer")
    assert client_for(bob).patch(url, {"tags": ["x"]}, format="json").status_code == 403


# The list directory.


def test_only_public_lists_are_listed(alice):
    make_list(alice, "Public tools")
    make_list(alice, "Unlisted tools", Visibility.UNLISTED)
    make_list(alice, "Private tools", Visibility.PRIVATE)
    expired = make_list(alice, "Expired tools")
    SharedList.objects.filter(pk=expired.pk).update(expires_at=timezone.now() - timedelta(1))
    leaving = User.objects.create_user("leaving@example.com", "pw-correct-horse-3")
    make_list(leaving, "Leaving tools")
    User.objects.filter(pk=leaving.pk).update(deleted_at=timezone.now())

    for user in (None, alice):  # not even the owner sees the others here
        assert titles(directory(user=user)) == ["Public tools"]
        assert titles(directory(user=user, q="tools")) == ["Public tools"]


def test_search_by_words_phrases_and_partial_titles(alice):
    make_list(alice, "Docker cheatsheets", description="Containers and images")
    make_list(alice, "Kubernetes", description="Docker in production")
    make_list(alice, "Cooking")
    assert titles(directory(q="docker")) == ["Docker cheatsheets", "Kubernetes"]  # title first
    assert titles(directory(q="containers")) == ["Docker cheatsheets"]
    assert titles(directory(q="dock")) == ["Docker cheatsheets"]  # partial word in a title
    assert titles(directory(q='"in production"')) == ["Kubernetes"]
    assert titles(directory(q="docker -containers")) == ["Kubernetes"]
    assert titles(directory(q="nothing-matches")) == []


def test_tag_filters_and_orderings(alice):
    old = make_list(alice, "B list", tags=["dev", "ai"])
    make_list(alice, "a list", tags=["dev"])
    make_list(alice, "C list", tags=["ai"])
    SharedList.objects.filter(pk=old.pk).update(updated_at=timezone.now() - timedelta(days=3))
    assert titles(directory(tags="dev")) == ["a list", "B list"]  # newest first
    assert titles(directory(tags="dev,AI")) == ["B list"]  # all of them, normalized
    assert titles(directory(ordering="title")) == ["a list", "B list", "C list"]
    assert directory(ordering="random").status_code == 400
    assert directory(tags="not ok!").status_code == 400
    assert directory(q="x" * 201).status_code == 400


def test_listed_items_show_owner_counts_and_your_role(alice, bob):
    shared_list = make_list(alice, "Shared tools", tags=["dev"])
    link_services.add_link(
        Principal(user=alice), shared_list.pk, destination_url="https://example.com/"
    )
    ListMembership.objects.create(shared_list=shared_list, user=bob, role="editor")

    anonymous = directory().json()["results"][0]
    assert anonymous["owner"] == {"display_name": alice.display_name}
    assert anonymous["link_count"] == 1 and anonymous["tags"] == ["dev"]
    assert anonymous["my_role"] is None and anonymous["permissions"] == ["view", "report"]
    assert directory(user=bob).json()["results"][0]["my_role"] == "editor"


def test_the_directory_is_rate_limited_per_ip(alice, bob, monkeypatch):
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"directory": "2/hour"})
    statuses = [directory().status_code, directory(user=alice).status_code]
    statuses.append(directory("groups", user=bob).status_code)  # signed in: still per IP
    assert statuses == [200, 200, 429]


# The group directory and tag facets.


def test_only_public_groups_with_counts_of_what_you_may_see(alice, bob):
    public_list = make_list(alice, "Public list")
    unlisted_list = make_list(alice, "Unlisted list", Visibility.UNLISTED)
    private_list = make_list(alice, "Private list", Visibility.PRIVATE)
    make_group(alice, "Portal", lists=[public_list, unlisted_list, private_list], tags=["dev"])
    make_group(alice, "Hidden portal", Visibility.UNLISTED)
    make_group(alice, "Private portal", Visibility.PRIVATE)

    (portal,) = directory("groups").json()["results"]
    assert (portal["title"], portal["list_count"], portal["tags"]) == ("Portal", 1, ["dev"])
    # The owner of the lists is shown more of them; a stranger isn't.
    assert directory("groups", user=alice).json()["results"][0]["list_count"] == 3
    assert directory("groups", user=bob).json()["results"][0]["list_count"] == 1
    assert titles(directory("groups", q="port")) == ["Portal"]
    assert titles(directory("groups", tags="dev")) == ["Portal"]


def test_tag_facets_count_public_resources_only(alice):
    make_list(alice, "One", tags=["dev", "ai"])
    make_list(alice, "Two", tags=["dev"])
    make_list(alice, "Secret", Visibility.PRIVATE, tags=["secret-project", "dev"])
    make_list(alice, "Unlisted", Visibility.UNLISTED, tags=["unlisted-only"])
    make_group(alice, "Group", tags=["dev", "design"])
    make_group(alice, "Private group", Visibility.PRIVATE, tags=["secret-group"])

    response = client_for().get(f"{URL}directory/tags/")
    assert response.json() == [
        {"tag": "dev", "count": 3},
        {"tag": "ai", "count": 1},
        {"tag": "design", "count": 1},
    ]
    prefixed = client_for().get(f"{URL}directory/tags/", {"prefix": "D"}).json()
    assert [t["tag"] for t in prefixed] == ["dev", "design"]


def test_the_search_column_follows_title_and_description(alice):
    """The generated column is maintained by PostgreSQL: renaming is enough to be found."""
    shared_list = make_list(alice, "Old name")
    list_services.update_list(
        Principal(user=alice), shared_list.pk, {"title": "Renamed", "description": "Zebras"}
    )
    assert titles(directory(q="zebras")) == ["Renamed"]
    assert titles(directory(q="old")) == []
    assert SharedLink.objects.count() == 0  # nothing else was touched
