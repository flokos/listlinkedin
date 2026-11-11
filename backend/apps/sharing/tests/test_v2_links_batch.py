"""Several links in one change (task 11.4): `POST /api/v2/lists/{code}/links/batch/`.

One lock, one revision when at least one link is added and none otherwise (invariant 3).
Links that can't be added are skipped and reported, and the rest still is.
"""

import threading

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django_tasks_db.models import DBTaskResult
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import User
from apps.sharing.domain import MAX_LINKS_PER_LIST
from apps.sharing.models import ListMembership, SharedLink, SharedList
from apps.sharing.selectors import Principal
from apps.sharing.services import links as link_services
from apps.sharing.services import lists as list_services
from apps.shortener.models import ShortRedirect
from apps.versioning.models import ListRevision

URL = "/api/v2/lists/"


@pytest.fixture
def alice(db):
    return User.objects.create_user("alice@example.com", "pw-correct-horse-1")


@pytest.fixture
def bob(db):
    return User.objects.create_user("bob@example.com", "pw-correct-horse-1")


def client_of(user=None) -> APIClient:
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


@pytest.fixture
def client(alice) -> APIClient:
    return client_of(alice)


@pytest.fixture
def shared_list(alice) -> SharedList:
    return list_services.create_list(Principal(user=alice), title="Tools")[0]


@pytest.fixture
def code(shared_list) -> str:
    return shared_list.public_code


def page(name: str) -> dict:
    return {"destination_url": f"https://example.com/{name}", "title": name}


def batch(client, code, links, **headers):
    return client.post(f"{URL}{code}/links/batch/", {"links": links}, format="json", **headers)


def listed(client, code) -> list[tuple[str, int]]:
    links = client.get(f"{URL}{code}/links/", {"page_size": 100}).json()["results"]
    return [(link["destination_url"], link["position"]) for link in links]


def revisions(shared_list) -> int:
    return ListRevision.objects.filter(shared_list=shared_list).count()


def skipped(response) -> list[tuple[int, str]]:
    return [(item["index"], item["reason"]) for item in response.json()["skipped"]]


def test_links_are_appended_in_order_as_one_revision(client, code, shared_list):
    client.post(f"{URL}{code}/links/", page("first"), format="json")
    before = revisions(shared_list)

    response = batch(client, code, [page("a"), page("b"), page("c")])

    assert response.status_code == 200, response.content
    body = response.json()
    assert [link["title"] for link in body["added"]] == ["a", "b", "c"]
    assert [link["position"] for link in body["added"]] == [1, 2, 3]
    assert all(link["short_url"] for link in body["added"])  # each has its short URL
    assert body["skipped"] == []
    assert listed(client, code) == [
        ("https://example.com/first", 0),
        ("https://example.com/a", 1),
        ("https://example.com/b", 2),
        ("https://example.com/c", 3),
    ]
    assert revisions(shared_list) == before + 1  # one change, however many links
    shared_list.refresh_from_db()
    assert response["ETag"] == f'"r{shared_list.head_revision}"'
    assert ShortRedirect.objects.filter(link__shared_list=shared_list).count() == 4


def test_what_cannot_be_added_is_skipped_and_the_rest_still_is(client, code, shared_list):
    client.post(f"{URL}{code}/links/", page("there"), format="json")
    before = revisions(shared_list)

    response = batch(
        client,
        code,
        [
            page("new"),
            page("there"),  # already in the list
            {"destination_url": "ftp://example.com/file"},  # not a web address
            page("new"),  # earlier in this request
            {"title": "no address"},
            {"destination_url": "https://example.com/long", "title": "x" * 300},
            {
                "destination_url": "  HTTPS://EXAMPLE.com/there  "
            },  # the same address, written otherwise
            page("also-new"),
        ],
    )

    assert response.status_code == 200, response.content
    body = response.json()
    assert [link["title"] for link in body["added"]] == ["new", "also-new"]
    assert skipped(response) == [
        (1, "duplicate"),
        (2, "invalid"),
        (3, "duplicate"),
        (4, "invalid"),
        (5, "invalid"),
        (6, "duplicate"),
    ]
    by_index = {item["index"]: item for item in body["skipped"]}
    assert by_index[1]["detail"] == "This URL is already in the list."
    assert by_index[2]["destination_url"] == "ftp://example.com/file"  # as it was sent
    assert by_index[4]["destination_url"] is None
    assert by_index[4]["detail"] == "This field is required."
    assert "255" in by_index[5]["detail"]
    assert revisions(shared_list) == before + 1
    assert [url for url, _ in listed(client, code)] == [
        "https://example.com/there",
        "https://example.com/new",
        "https://example.com/also-new",
    ]


def test_nothing_added_writes_no_revision(client, code, shared_list):
    links = [page("a"), page("b")]
    first = batch(client, code, links)
    after_first = revisions(shared_list)

    again = batch(client, code, links)  # the same request once more: nothing new

    assert again.status_code == 200
    assert again.json()["added"] == []
    assert skipped(again) == [(0, "duplicate"), (1, "duplicate")]
    assert revisions(shared_list) == after_first
    assert again["ETag"] == first["ETag"]  # the list didn't change
    assert len(listed(client, code)) == 2

    only_bad = batch(client, code, [{"destination_url": "not a url"}])
    assert only_bad.status_code == 200 and skipped(only_bad) == [(0, "invalid")]
    assert revisions(shared_list) == after_first


def test_a_list_takes_links_until_it_is_full(client, code, shared_list):
    for n in range(MAX_LINKS_PER_LIST - 2):
        link_services.add_link_on(shared_list, destination_url=f"https://e{n}.example/")
    client.post(f"{URL}{code}/links/", page("there"), format="json")

    response = batch(client, code, [page("fits"), page("there"), page("too-many"), page("more")])

    assert [link["title"] for link in response.json()["added"]] == ["fits"]
    # A link already there is reported as that, full list or not.
    assert skipped(response) == [(1, "duplicate"), (2, "list_full"), (3, "list_full")]
    assert response.json()["skipped"][1]["detail"] == "A list can contain at most 100 links."
    assert SharedLink.objects.filter(shared_list=shared_list, deleted_at=None).count() == 100


def test_a_batch_is_always_appended_and_only_carries_link_fields(client, code):
    batch(client, code, [page("a")])
    response = batch(
        client,
        code,
        [
            {
                "destination_url": "https://example.com/b",
                "description": "About b",
                "position": 0,  # ignored: a batch goes at the end
                "id": "00000000-0000-0000-0000-000000000000",
                "short_url": "https://evil.example/",
            }
        ],
    )
    (added,) = response.json()["added"]
    assert added["position"] == 1 and added["description"] == "About b"
    assert added["title"] is None  # none sent: the page's own shows once fetched
    assert added["id"] != "00000000-0000-0000-0000-000000000000"
    assert "evil.example" not in added["short_url"]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"links": []},
        {"links": "https://example.com/"},
        {"links": ["https://example.com/"]},
        {"links": [{"destination_url": f"https://example.com/{n}"} for n in range(101)]},
    ],
)
def test_a_malformed_request_is_refused_whole(client, code, shared_list, body):
    before = revisions(shared_list)
    response = client.post(f"{URL}{code}/links/batch/", body, format="json")
    assert response.status_code == 400, response.content
    assert "links" in response.json()
    assert revisions(shared_list) == before


def test_only_editors_and_owners_may_add(alice, bob, code, shared_list):
    links = [page("a")]
    # A private list: a stranger and a visitor don't learn that it exists.
    assert batch(client_of(bob), code, links).status_code == 404
    assert batch(client_of(), code, links).status_code == 404

    membership = ListMembership.objects.create(shared_list=shared_list, user=bob, role="viewer")
    assert batch(client_of(bob), code, links).status_code == 403
    assert SharedLink.objects.filter(shared_list=shared_list).count() == 0

    membership.role = "editor"
    membership.save()
    response = batch(client_of(bob), code, links)
    assert response.status_code == 200 and len(response.json()["added"]) == 1
    revision = ListRevision.objects.filter(shared_list=shared_list).order_by("-number").first()
    assert revision.created_by == bob  # the history names who added them

    # Anyone can see an unlisted list; that isn't a right to add to it.
    SharedList.objects.filter(pk=shared_list.pk).update(visibility="unlisted")
    assert batch(client_of(), code, [page("b")]).status_code in (401, 403)
    assert SharedLink.objects.filter(shared_list=shared_list).count() == 1


def test_a_stale_if_match_changes_nothing(client, code, shared_list):
    stale = batch(client, code, [page("a")])["ETag"]
    batch(client, code, [page("b")])
    before = revisions(shared_list)

    refused = batch(client, code, [page("c")], HTTP_IF_MATCH=stale)

    assert refused.status_code == 412, refused.content
    assert refused.json()["code"] == "revision_mismatch"
    assert revisions(shared_list) == before
    assert len(listed(client, code)) == 2

    shared_list.refresh_from_db()
    current = f'"r{shared_list.head_revision}"'
    assert batch(client, code, [page("c")], HTTP_IF_MATCH=current).status_code == 200


def test_each_added_link_gets_its_page_fetched_after_the_commit(
    client, code, django_capture_on_commit_callbacks
):
    def queued() -> list[str]:
        tasks = DBTaskResult.objects.filter(task_path__endswith="fetch_link_metadata")
        return sorted(task.args_kwargs["args"][1] for task in tasks)

    with django_capture_on_commit_callbacks(execute=True):
        batch(client, code, [page("a"), page("a"), {"destination_url": "nope"}, page("b")])
        assert queued() == []  # not before the commit
    assert queued() == ["https://example.com/a", "https://example.com/b"]  # only what was added


def test_batches_have_a_rate_limit_of_their_own(client, code, monkeypatch):
    monkeypatch.setattr(
        ScopedRateThrottle, "THROTTLE_RATES", {"link_batch": "2/hour", "list_manage": "600/hour"}
    )
    statuses = [batch(client, code, [page(str(n))]).status_code for n in range(3)]
    assert statuses == [200, 200, 429]
    # Single links are counted separately.
    assert client.post(f"{URL}{code}/links/", page("single"), format="json").status_code == 201


def test_the_cost_grows_only_with_the_links_added(client, code):
    def cost(links) -> int:
        with CaptureQueriesContext(connection) as captured:
            assert batch(client, code, links).status_code == 200
        return len(captured.captured_queries)

    ten = cost([page(f"a{n}") for n in range(10)])
    twenty = cost([page(f"b{n}") for n in range(20)])
    per_link = (twenty - ten) / 10
    assert per_link <= 4, f"{per_link} queries per added link"
    # Links that are skipped cost nothing: one read of the list's addresses finds them all.
    duplicates = cost([page(f"b{n}") for n in range(20)])
    assert duplicates < ten - 10


@pytest.mark.django_db(transaction=True)
def test_a_batch_and_single_adds_at_the_same_time_keep_the_list_whole():
    owner = User.objects.create_user("owner@example.com", "pw-correct-horse-1")
    principal = Principal(user=owner)
    shared_list, _ = list_services.create_list(principal, title="Race")
    shared = "https://example.com/shared"  # in the batch, and added singly at the same time
    items = [
        (n, {"destination_url": url})
        for n, url in enumerate([shared, *(f"https://example.com/b{n}" for n in range(5))])
    ]
    barrier = threading.Barrier(3)
    errors, outcomes = [], {}

    def work(name):
        try:
            barrier.wait()
            if name == "batch":
                outcomes[name] = link_services.add_links(principal, shared_list.pk, items)
            else:
                url = shared if name == "same" else "https://example.com/other"
                link_services.add_link(principal, shared_list.pk, destination_url=url)
                outcomes[name] = "added"
        except Exception as exc:  # noqa: BLE001 - reported below
            errors.append((name, exc))
        finally:
            connection.close()

    threads = [threading.Thread(target=work, args=(name,)) for name in ("batch", "same", "other")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    live = SharedLink.objects.filter(shared_list=shared_list, deleted_at__isnull=True)
    urls = list(live.values_list("destination_url", flat=True))
    assert len(urls) == len(set(urls)) == 7  # the shared address exactly once
    assert sorted(live.values_list("position", flat=True)) == list(range(7))
    # Whoever came second found the address there: the single add fails, or the batch skips it.
    added, skipped_items = outcomes["batch"]
    if errors:
        assert [name for name, _ in errors] == ["same"]
        assert len(added) == 6 and skipped_items == []
    else:
        assert len(added) == 5 and skipped_items == [(0, "duplicate")]
    # One revision per change that added something, and no number twice.
    numbers = list(
        ListRevision.objects.filter(shared_list=shared_list).values_list("number", flat=True)
    )
    assert len(numbers) == len(set(numbers)) == 1 + 1 + 1 + (0 if errors else 1)


def test_openapi_describes_the_batch(db):
    schema = Client().get("/api/schema/", {"format": "json"}).json()
    operation = schema["paths"]["/api/v2/lists/{code}/links/batch/"]["post"]
    assert {"200", "403", "404", "412"} <= set(operation["responses"])
    result = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    properties = schema["components"]["schemas"][result.rsplit("/", 1)[-1]]["properties"]
    assert set(properties) == {"added", "skipped"}
    names = {parameter["name"] for parameter in operation["parameters"]}
    assert {"code", "If-Match"} <= names
