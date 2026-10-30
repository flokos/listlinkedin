"""Links v2 (task 2.1): stored order, tombstones, idempotent creation, and the migration that
numbers V1 links (docs/v2/04-DOMAIN-MODEL.md, 05-DATABASE-DESIGN.md, ADR-013)."""

import threading
import uuid
from datetime import timedelta

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.sharing import services as legacy_services
from apps.sharing.domain import MAX_LINKS_PER_LIST
from apps.sharing.models import SharedLink, SharedList
from apps.sharing.selectors import Principal
from apps.sharing.services import links as link_services
from apps.sharing.services import lists as list_services
from apps.shortener.models import ShortRedirect

URL = "/api/v2/lists/"


@pytest.fixture
def alice(db):
    return User.objects.create_user("alice@example.com", "pw-correct-horse-1")


@pytest.fixture
def client(alice) -> APIClient:
    client = APIClient()
    client.force_authenticate(alice)
    return client


@pytest.fixture
def code(alice) -> str:
    shared_list, _ = list_services.create_list(Principal(user=alice), title="Tools")
    return shared_list.public_code


def links_url(code: str, link_id=None) -> str:
    return f"{URL}{code}/links/" + (f"{link_id}/" if link_id else "")


def add(client, code, url, **data):
    response = client.post(links_url(code), {"destination_url": url, **data}, format="json")
    assert response.status_code == 201, response.content
    return response.json()


def listed(client, code):
    return [
        (link["title"], link["position"]) for link in client.get(links_url(code)).json()["results"]
    ]


def test_links_are_appended_and_listed_in_their_stored_order(client, code):
    for name in ("a", "b", "c"):
        add(client, code, f"https://example.com/{name}", title=name)
    assert listed(client, code) == [("a", 0), ("b", 1), ("c", 2)]


def test_a_link_can_be_inserted_at_a_position(client, code):
    for name in ("a", "b"):
        add(client, code, f"https://example.com/{name}", title=name)
    add(client, code, "https://example.com/first", title="first", position=0)
    add(client, code, "https://example.com/far", title="far", position=99)  # clamped
    assert listed(client, code) == [("first", 0), ("a", 1), ("b", 2), ("far", 3)]


def test_deleting_keeps_a_tombstone_and_closes_the_gap(client, code):
    a, b, c = (add(client, code, f"https://example.com/{n}", title=n) for n in "abc")
    assert client.delete(links_url(code, b["id"])).status_code == 204

    assert listed(client, code) == [("a", 0), ("c", 1)]
    tombstone = SharedLink.objects.get(pk=b["id"])
    assert tombstone.deleted_at is not None and tombstone.position is None
    assert client.get(f"{URL}{code}/").json()["link_count"] == 2
    assert client.get(URL).json()["results"][0]["link_count"] == 2
    # The short URL stays reserved but answers 404; the tombstone can't be edited or deleted.
    short_path = b["short_url"].split("/", 3)[3]
    assert APIClient().get(f"/{short_path}").status_code == 404
    assert client.patch(links_url(code, b["id"]), {"title": "x"}, format="json").status_code == 404
    assert client.delete(links_url(code, b["id"])).status_code == 404
    assert ShortRedirect.objects.filter(link_id=b["id"]).exists()


def test_a_deleted_url_can_be_added_again_as_a_new_link(client, code):
    first = add(client, code, "https://example.com/again")
    client.delete(links_url(code, first["id"]))
    second = add(client, code, "https://example.com/again")
    assert second["id"] != first["id"] and second["short_url"] != first["short_url"]
    duplicate = client.post(
        links_url(code), {"destination_url": "https://example.com/again"}, format="json"
    )
    assert duplicate.status_code == 400


def test_the_link_limit_counts_live_links_only(client, code):
    shared_list = SharedList.objects.get(public_code=code)
    for i in range(MAX_LINKS_PER_LIST):
        link_services.add_link_on(shared_list, destination_url=f"https://example.com/{i}")
    assert (
        client.post(
            links_url(code), {"destination_url": "https://example.com/x"}, format="json"
        ).status_code
        == 400
    )
    link = SharedLink.objects.get(shared_list=shared_list, position=0)
    client.delete(links_url(code, link.pk))
    add(client, code, "https://example.com/x")


def test_retrying_with_the_same_idempotency_key_returns_the_first_link(client, code):
    key = str(uuid.uuid4())
    body = {"destination_url": "https://example.com/once"}
    first = client.post(links_url(code), body, format="json", HTTP_IDEMPOTENCY_KEY=key)
    again = client.post(links_url(code), body, format="json", HTTP_IDEMPOTENCY_KEY=key)
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json()["id"] == first.json()["id"]
    assert SharedLink.objects.count() == 1
    bad = client.post(links_url(code), body, format="json", HTTP_IDEMPOTENCY_KEY="nope")
    assert bad.status_code == 400


def test_descriptions_and_the_v2_representation(client, code):
    link = add(client, code, "https://example.com/d", description="  Notes  ")
    assert link["description"] == "Notes"
    assert link["position"] == 0 and link["source_link_id"] is None
    cleared = client.patch(links_url(code, link["id"]), {"description": ""}, format="json")
    assert cleared.json()["description"] is None
    too_long = {"description": "x" * 1001}
    assert client.patch(links_url(code, link["id"]), too_long, format="json").status_code == 400
    moved = client.patch(links_url(code, link["id"]), {"position": 3}, format="json")
    assert moved.status_code == 400  # moving is task 2.2's reorder endpoint


def test_the_v1_api_keeps_newest_first_and_uses_tombstones_too(db):
    shared_list, token = legacy_services.create_list(title="Legacy")
    old = legacy_services.add_link(shared_list, destination_url="https://example.com/old")
    new = legacy_services.add_link(shared_list, destination_url="https://example.com/new")
    v1 = APIClient().get(f"/api/v1/lists/{shared_list.public_code}/links/").json()["results"]
    assert [link["id"] for link in v1] == [str(new.pk), str(old.pk)]
    assert "position" not in v1[0]  # the V1 representation is unchanged

    legacy_services.delete_link(shared_list, old.pk)
    assert SharedLink.objects.get(pk=old.pk).deleted_at is not None
    assert SharedLink.objects.get(pk=new.pk).position == 0


def test_the_database_enforces_the_tombstone_and_order_rules(code):
    shared_list = SharedList.objects.get(public_code=code)
    link = link_services.add_link_on(shared_list, destination_url="https://example.com/a")
    with pytest.raises(IntegrityError), transaction.atomic():
        SharedLink.objects.filter(pk=link.pk).update(deleted_at=timezone.now())  # keeps position
    with pytest.raises(IntegrityError), transaction.atomic():
        SharedLink.objects.create(
            shared_list=shared_list, destination_url="https://example.com/b", position=0
        )
        connection.check_constraints()  # deferred: checked at commit; force it here
    with pytest.raises(IntegrityError), transaction.atomic():
        SharedLink.objects.create(
            shared_list=shared_list, destination_url="https://example.com/a", position=1
        )


@pytest.mark.django_db(transaction=True)
def test_concurrent_adds_and_deletes_keep_positions_dense():
    owner = User.objects.create_user("owner@example.com", "pw-correct-horse-1")
    shared_list, _ = list_services.create_list(Principal(user=owner), title="Race")
    seeded = [
        link_services.add_link_on(shared_list, destination_url=f"https://example.com/s{i}")
        for i in range(6)
    ]
    principal = Principal(user=owner)
    barrier = threading.Barrier(6)
    errors = []

    def work(i):
        try:
            barrier.wait()
            if i % 2:
                link_services.delete_link(principal, shared_list.pk, seeded[i].pk)
            else:
                link_services.add_link(
                    principal, shared_list.pk, destination_url=f"https://example.com/n{i}"
                )
        except Exception as exc:  # noqa: BLE001 - reported below
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=work, args=(i,)) for i in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    positions = sorted(
        SharedLink.objects.filter(shared_list=shared_list, deleted_at__isnull=True).values_list(
            "position", flat=True
        )
    )
    assert positions == list(range(6))  # 6 seeded - 3 deleted + 3 added


BEFORE = [("sharing", "0002_list_ownership")]
AFTER = [("sharing", "0005_link_constraints")]


@pytest.mark.django_db(transaction=True)
def test_the_migration_numbers_existing_links_newest_first():
    executor = MigrationExecutor(connection)
    executor.migrate(BEFORE)
    state = executor.loader.project_state(BEFORE).apps
    OldList, OldLink = (
        state.get_model("sharing", "SharedList"),
        state.get_model("sharing", "SharedLink"),
    )
    now = timezone.now()
    lists = [
        OldList.objects.create(
            public_code=f"MigrateCode{i:05d}",
            owner_token_hash=str(i) * 64,
            title=f"L{i}",
            slug=f"l{i}",
            visibility="unlisted",
            expires_at=now + timedelta(days=5),
        )
        for i in range(2)
    ]
    for shared_list in lists:
        for age in (3, 1, 2):  # created out of order
            OldLink.objects.create(
                shared_list=shared_list,
                destination_url=f"https://example.com/{age}",
                created_at=now - timedelta(days=age),
            )

    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(AFTER)
    NewLink = executor.loader.project_state(AFTER).apps.get_model("sharing", "SharedLink")
    for shared_list in lists:
        order = list(
            NewLink.objects.filter(shared_list_id=shared_list.pk)
            .order_by("position")
            .values_list("destination_url", "position")
        )
        assert order == [
            ("https://example.com/1", 0),
            ("https://example.com/2", 1),
            ("https://example.com/3", 2),
        ]

    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes())


def test_display_applies_user_then_fetched_then_fallback(client, code):
    plain = add(client, code, "https://www.example.com/page")
    assert plain["display"] == {
        "title": "example.com",  # no title, nothing fetched: the host
        "description": None,
        "icon_url": None,
        "site_name": "example.com",
    }
    # Since task 7.3 fetched values count only when recorded as a finished fetch of the link's
    # current URL (`link_url`, `status`), so an old page's values never show after a URL edit
    # (test_v2_metadata.py). The precedence tested here is unchanged.
    fetched = {
        "link_url": "https://www.example.com/page",
        "status": "ready",
        "title": "Fetched title",
        "description": "Fetched description",
        "icon": "meta/ab/ab12.webp",
        "site_name": "Example",
    }
    SharedLink.objects.filter(pk=plain["id"]).update(metadata=fetched)
    link = client.get(links_url(code)).json()["results"][0]
    assert link["display"] == {
        "title": "Fetched title",
        "description": "Fetched description",
        "icon_url": "/media/meta/ab/ab12.webp",
        "site_name": "Example",
    }
    assert link["title"] is None and link["icon_url"] is None  # fetched data stays apart

    SharedLink.objects.filter(pk=plain["id"]).update(icon="icons/cd/cd34.webp")
    mine = client.patch(
        links_url(code, plain["id"]), {"title": "Mine", "description": "My words"}, format="json"
    ).json()
    assert mine["display"] == {
        "title": "Mine",
        "description": "My words",
        "icon_url": "/media/icons/cd/cd34.webp",
        "site_name": "Example",
    }
