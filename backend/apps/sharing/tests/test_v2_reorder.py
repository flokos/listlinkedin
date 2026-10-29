"""Reordering links and moving them to another list (task 2.2; docs/v2/adr/ADR-005, K4)."""

import threading

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.sharing import services as legacy_services
from apps.sharing.domain import MAX_LINKS_PER_LIST
from apps.sharing.models import ListMembership, SharedLink, SharedList
from apps.sharing.policy import Visibility
from apps.sharing.selectors import Principal
from apps.sharing.services import links as link_services
from apps.sharing.services import lists as list_services

URL = "/api/v2/lists/"


def make_user(email):
    return User.objects.create_user(email, "pw-correct-horse-1")


@pytest.fixture
def alice(db):
    return make_user("alice@example.com")


@pytest.fixture
def bob(db):
    return make_user("bob@example.com")


def client_for(user=None) -> APIClient:
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return client


def new_list(owner, title="Tools", names="abcde", **settings) -> SharedList:
    shared_list, _ = list_services.create_list(Principal(user=owner), title=title, **settings)
    for name in names:
        link_services.add_link_on(
            shared_list, destination_url=f"https://example.com/{title}/{name}", title=name
        )
    return shared_list


def link(shared_list, title) -> SharedLink:
    return SharedLink.objects.get(shared_list=shared_list, title=title, deleted_at__isnull=True)


def order(shared_list) -> str:
    live = SharedLink.objects.filter(shared_list=shared_list, deleted_at__isnull=True)
    return "".join(live.order_by("position").values_list("title", flat=True))


def reorder(client, shared_list, title, to_index):
    body = {"link": str(link(shared_list, title).pk), "to_index": to_index}
    return client.post(f"{URL}{shared_list.public_code}/reorder/", body, format="json")


@pytest.mark.parametrize(
    ("title", "to_index", "expected"),
    [
        ("b", 3, "acdbe"),  # down
        ("d", 0, "dabce"),  # up to the top
        ("a", 99, "bcdea"),  # clamped to the end
        ("c", 2, "abcde"),  # same place: nothing changes
    ],
)
def test_a_move_puts_one_link_at_its_new_index(alice, title, to_index, expected):
    shared_list = new_list(alice)
    response = reorder(client_for(alice), shared_list, title, to_index)
    assert response.status_code == 200
    assert "".join(item["title"] for item in response.json()) == expected
    assert [item["position"] for item in response.json()] == [0, 1, 2, 3, 4]
    assert order(shared_list) == expected


def test_who_may_reorder(alice, bob):
    shared_list = new_list(alice, visibility=Visibility.UNLISTED)
    assert reorder(client_for(), shared_list, "a", 2).status_code == 401
    assert reorder(client_for(bob), shared_list, "a", 2).status_code == 403
    ListMembership.objects.create(shared_list=shared_list, user=bob, role="viewer")
    assert reorder(client_for(bob), shared_list, "a", 2).status_code == 403
    ListMembership.objects.filter(user=bob).update(role="editor")
    assert reorder(client_for(bob), shared_list, "a", 2).status_code == 200
    private = new_list(alice, "Private", names="xy")
    assert reorder(client_for(bob), private, "x", 1).status_code == 404


def test_deleted_or_foreign_links_cannot_be_moved(alice):
    shared_list = new_list(alice)
    other = new_list(alice, "Other", names="z")
    client = client_for(alice)
    gone = link(shared_list, "b")
    link_services.delete_link_on(shared_list, gone.pk)
    for link_id in (gone.pk, link(other, "z").pk):
        body = {"link": str(link_id), "to_index": 0}
        response = client.post(f"{URL}{shared_list.public_code}/reorder/", body, format="json")
        assert response.status_code == 404
    assert order(shared_list) == "acde"


def test_a_legacy_edit_link_can_reorder_its_list(db):
    shared_list, token = legacy_services.create_list(title="Legacy")
    for name in "ab":
        legacy_services.add_link(shared_list, destination_url=f"https://example.com/{name}")
    first = SharedLink.objects.get(shared_list=shared_list, position=0)
    response = APIClient().post(
        f"{URL}{shared_list.public_code}/reorder/",
        {"link": str(first.pk), "to_index": 1},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert response.status_code == 200
    assert SharedLink.objects.get(pk=first.pk).position == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_moves_of_different_links_are_serialized():
    owner = make_user("owner@example.com")
    shared_list = new_list(owner, names="abcdefgh")
    principal = Principal(user=owner)
    moves = [("a", 7), ("h", 0), ("c", 5), ("f", 1), ("b", 6), ("g", 2)]
    ids = {title: link(shared_list, title).pk for title, _ in moves}
    barrier = threading.Barrier(len(moves))
    errors = []

    def move(title, to_index):
        try:
            barrier.wait()
            link_services.move_link(principal, shared_list.pk, ids[title], to_index)
        except Exception as exc:  # noqa: BLE001 - reported below
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=move, args=m) for m in moves]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    live = SharedLink.objects.filter(shared_list=shared_list, deleted_at__isnull=True)
    assert sorted(live.values_list("position", flat=True)) == list(range(8))
    assert sorted(order(shared_list)) == list("abcdefgh")  # nothing lost or duplicated


def move_to(client, source, title, target_code):
    path = f"{URL}{source.public_code}/links/{link(source, title).pk}/move-to-list/"
    return client.post(path, {"list": target_code}, format="json")


def test_moving_to_another_list_copies_and_deletes(alice):
    source = new_list(alice, "Source", names="abc")
    target = new_list(alice, "Target", names="xy")
    moved = link(source, "b")
    response = move_to(client_for(alice), source, "b", target.public_code)

    assert response.status_code == 201
    copy = response.json()
    assert copy["id"] != str(moved.pk) and copy["position"] == 2 and copy["title"] == "b"
    assert order(source) == "ac" and order(target) == "xyb"
    tombstone = SharedLink.objects.get(pk=moved.pk)
    assert tombstone.deleted_at is not None
    short_code = tombstone.redirects.get().code
    assert client_for(alice).get(f"/r/{short_code}").status_code == 404
    assert copy["short_url"].rsplit("/", 1)[-1] != short_code


def test_moving_needs_edit_rights_on_both_lists(alice, bob):
    source = new_list(alice, "Source", names="ab", visibility=Visibility.UNLISTED)
    readable = new_list(bob, "Bob's", names="", visibility=Visibility.UNLISTED)
    hidden = new_list(bob, "Hidden", names="")
    client = client_for(alice)
    assert move_to(client, source, "a", readable.public_code).status_code == 403
    assert move_to(client, source, "a", hidden.public_code).status_code == 404
    assert move_to(client, source, "a", "NoSuchList000000").status_code == 404
    ListMembership.objects.create(shared_list=readable, user=alice, role="editor")
    assert move_to(client, source, "a", readable.public_code).status_code == 201
    # An editor of the target only can't take links out of someone else's list.
    assert move_to(client_for(bob), source, "b", readable.public_code).status_code == 403
    assert order(source) == "b"


def test_moving_respects_the_target_rules(alice):
    source = new_list(alice, "Source", names="ab")
    full = new_list(alice, "Full", names="")
    for i in range(MAX_LINKS_PER_LIST):
        link_services.add_link_on(full, destination_url=f"https://example.com/full/{i}")
    twin = new_list(alice, "Twin", names="")
    link_services.add_link_on(twin, destination_url="https://example.com/Source/a")
    client = client_for(alice)
    assert move_to(client, source, "a", full.public_code).status_code == 400
    assert move_to(client, source, "a", twin.public_code).status_code == 400  # duplicate URL
    assert move_to(client, source, "a", source.public_code).status_code == 400  # same list
    assert order(source) == "ab"  # nothing changed


@pytest.mark.django_db(transaction=True)
def test_opposite_moves_at_the_same_time_do_not_deadlock():
    owner = make_user("owner@example.com")
    left = new_list(owner, "Left", names="abc")
    right = new_list(owner, "Right", names="xyz")
    principal = Principal(user=owner)
    jobs = [(left, right, "a"), (right, left, "x"), (left, right, "b"), (right, left, "y")]
    ids = {title: link(src, title).pk for src, _, title in jobs}
    barrier = threading.Barrier(len(jobs))
    errors = []

    def move(source, target, title):
        try:
            barrier.wait()
            link_services.move_link_to_list(principal, source.pk, ids[title], target.pk)
        except Exception as exc:  # noqa: BLE001 - reported below
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=move, args=job) for job in jobs]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
    assert sorted(order(left)) == list("cxy") and sorted(order(right)) == list("abz")
    for shared_list in (left, right):
        live = SharedLink.objects.filter(shared_list=shared_list, deleted_at__isnull=True)
        assert sorted(live.values_list("position", flat=True)) == [0, 1, 2]
