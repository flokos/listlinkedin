"""The revisions API (task 3.3; docs/v2/09-API-DESIGN.md#revisions-and-restore): history,
one revision with its diff, and restore (revive, tombstone, reposition) behind If-Match."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.sharing import services as legacy_services
from apps.sharing.models import ListMembership, SharedLink, SharedList
from apps.versioning.models import ListRevision

URL = "/api/v2/lists/"


@pytest.fixture
def alice(db):
    return User.objects.create_user("alice@example.com", "pw-correct-horse-1", display_name="Alice")


@pytest.fixture
def bob(db):
    return User.objects.create_user("bob@example.com", "pw-correct-horse-1", display_name="Bob")


def client_for(user=None, **headers) -> APIClient:
    client = APIClient(**headers)
    if user:
        client.force_authenticate(user)
    return client


class Lst:
    """A list driven through the API, as its owner would."""

    def __init__(self, client, title="Tools"):
        self.client = client
        self.code = client.post(URL, {"title": title}, format="json").json()["code"]

    def add(self, name, **extra):
        body = {"destination_url": f"https://{name}.example/", "title": name, **extra}
        response = self.client.post(f"{URL}{self.code}/links/", body, format="json")
        assert response.status_code == 201, response.content
        return response.json()

    def links(self):
        return self.client.get(f"{URL}{self.code}/links/").json()["results"]

    def titles(self):
        return [link["title"] for link in self.links()]

    def etag(self):
        return self.client.get(f"{URL}{self.code}/")["ETag"]

    def restore(self, number, if_match="current"):
        headers = (
            {}
            if if_match is None
            else {"HTTP_IF_MATCH": self.etag() if if_match == "current" else if_match}
        )
        return self.client.post(
            f"{URL}{self.code}/restore/", {"revision": number}, format="json", **headers
        )

    def history(self, client=None):
        return (client or self.client).get(f"{URL}{self.code}/revisions/")


def test_history_lists_revisions_newest_first_with_authors(alice):
    lst = Lst(client_for(alice))
    lst.add("a")
    lst.client.patch(f"{URL}{lst.code}/", {"title": "Dev tools"}, format="json")
    response = lst.history()

    assert response.status_code == 200 and response["ETag"] == '"r3"'
    entries = response.json()["results"]
    assert [(e["number"], e["kind"]) for e in entries] == [
        (3, "edited"),
        (2, "edited"),
        (1, "created"),
    ]
    assert entries[0]["author"] == {"display_name": "Alice"}
    assert entries[0]["summary"]["list"] == ["title"]
    assert entries[1]["summary"]["added"] == 1


def test_authors_of_edit_links_baselines_and_deleted_accounts(alice, bob):
    legacy, token = legacy_services.create_list(title="Legacy")
    client = client_for(HTTP_AUTHORIZATION=f"Bearer {token}")
    entries = client.get(f"{URL}{legacy.public_code}/revisions/").json()["results"]
    assert entries[0]["author"] == "edit link"

    lst = Lst(client_for(alice))
    shared_list = SharedList.objects.get(public_code=lst.code)
    ListMembership.objects.create(shared_list=shared_list, user=bob, role="editor")
    Lst.add(type("L", (), {"client": client_for(bob), "code": lst.code})(), "from-bob")
    bob.deleted_at = bob.date_joined
    bob.save()
    ListRevision.objects.create(  # what versioning.0003 writes for lists from before V2
        shared_list=SharedList.objects.create(
            public_code="Baseline00000001", owner=alice, title="Old", visibility="private"
        ),
        number=1,
        schema_version=1,
        kind="migrated",
        snapshot={"schema_version": 1, "list": {"title": "Old", "description": ""}, "links": []},
    )
    assert lst.history().json()["results"][0]["author"] == {"display_name": "Deleted account"}
    old = client_for(alice).get(f"{URL}Baseline00000001/revisions/").json()["results"]
    assert old[0]["author"] is None


def test_who_may_see_history(alice, bob):
    lst = Lst(client_for(alice))
    lst.client.patch(f"{URL}{lst.code}/", {"visibility": "unlisted"}, format="json")
    assert lst.history(client_for()).status_code == 401
    assert lst.history(client_for(bob)).status_code == 403  # can view the list, not its history
    shared_list = SharedList.objects.get(public_code=lst.code)
    membership = ListMembership.objects.create(shared_list=shared_list, user=bob, role="viewer")
    assert lst.history(client_for(bob)).status_code == 403
    membership.role = "editor"
    membership.save()
    assert lst.history(client_for(bob)).status_code == 200
    private = Lst(client_for(alice), "Private")
    assert private.history(client_for(bob)).status_code == 404


def test_a_revision_has_its_snapshot_and_diff(alice):
    lst = Lst(client_for(alice))
    a = lst.add("a")
    b = lst.add("b")
    lst.add("c")
    lst.client.patch(f"{URL}{lst.code}/links/{a['id']}/", {"title": "A!"}, format="json")
    lst.client.delete(f"{URL}{lst.code}/links/{b['id']}/")
    lst.client.post(f"{URL}{lst.code}/reorder/", {"link": a["id"], "to_index": 1}, format="json")

    detail = lst.client.get(f"{URL}{lst.code}/revisions/7/").json()
    assert [link["title"] for link in detail["snapshot"]["links"]] == ["c", "A!"]
    changes = detail["diff_from_previous"]["links"]
    # [A!, c] became [c, A!]: one of the two had to move (which one is a tie).
    assert [c["changes"] for c in changes] == [["moved"]]
    modified = lst.client.get(f"{URL}{lst.code}/revisions/5/").json()["diff_from_previous"]
    assert modified["links"][0]["fields"] == {"title": {"before": "a", "after": "A!"}}
    removed = lst.client.get(f"{URL}{lst.code}/revisions/6/").json()["diff_from_previous"]
    assert [(c["title"], c["changes"]) for c in removed["links"]] == [("b", ["removed"])]
    first = lst.client.get(f"{URL}{lst.code}/revisions/1/").json()
    assert first["diff_from_previous"] == {"list": {}, "links": []}
    assert lst.client.get(f"{URL}{lst.code}/revisions/99/").status_code == 404


def test_restore_revives_deletes_and_reorders(alice):
    lst = Lst(client_for(alice))
    lst.client.patch(f"{URL}{lst.code}/", {"visibility": "unlisted"}, format="json")
    a = lst.add("a")
    b = lst.add("b")  # revision 3: [a, b]
    short_b = b["short_url"].split("/", 3)[3]
    lst.client.delete(f"{URL}{lst.code}/links/{b['id']}/")
    c = lst.add("c")
    lst.client.post(f"{URL}{lst.code}/reorder/", {"link": c["id"], "to_index": 0}, format="json")
    lst.client.patch(
        f"{URL}{lst.code}/", {"title": "Renamed", "visibility": "public"}, format="json"
    )
    assert APIClient().get(f"/{short_b}").status_code == 404
    head_before = int(lst.etag().strip('"r'))

    response = lst.restore(3)

    assert response.status_code == 200
    assert response.json() == {"revision": head_before + 1, "changed": True}
    assert response["ETag"] == f'"r{head_before + 1}"'
    assert lst.titles() == ["a", "b"]
    assert [link["id"] for link in lst.links()] == [a["id"], b["id"]]  # the same rows
    assert APIClient().get(f"/{short_b}").status_code == 302  # its short URL works again
    assert SharedLink.objects.get(pk=c["id"]).deleted_at is not None  # added since: deleted
    detail = lst.client.get(f"{URL}{lst.code}/").json()
    assert detail["title"] == "Tools"
    assert detail["visibility"] == "unlisted"  # settings aren't restored
    newest = lst.history().json()["results"][0]
    assert (newest["kind"], newest["restored_from"]) == ("restored", 3)
    # History only grows: every earlier revision is still there.
    assert ListRevision.objects.filter(shared_list__public_code=lst.code).count() == head_before + 1


def test_restore_needs_a_current_if_match(alice):
    lst = Lst(client_for(alice))
    lst.add("a")
    lst.add("b")
    missing = lst.restore(2, if_match=None)
    assert missing.status_code == 428 and missing.json()["code"] == "precondition_required"
    stale = lst.restore(2, if_match='"r1"')
    assert stale.status_code == 412 and stale.json()["head_revision"] == 3
    assert lst.titles() == ["a", "b"]  # nothing changed
    assert lst.restore(99).status_code == 404


def test_restoring_the_current_content_changes_nothing(alice):
    lst = Lst(client_for(alice))
    lst.add("a")
    lst.client.patch(f"{URL}{lst.code}/", {"title": "Tools"}, format="json")  # a no-op edit
    response = lst.restore(2)
    assert response.json() == {"revision": 2, "changed": False}
    assert ListRevision.objects.filter(shared_list__public_code=lst.code).count() == 2


def test_restore_handles_swapped_and_reused_urls(alice):
    lst = Lst(client_for(alice))
    a = lst.add("a")
    b = lst.add("b")  # revision 3: a → a.example, b → b.example
    links = f"{URL}{lst.code}/links/"
    lst.client.patch(
        f"{links}{a['id']}/", {"destination_url": "https://tmp.example/"}, format="json"
    )
    lst.client.patch(f"{links}{b['id']}/", {"destination_url": "https://a.example/"}, format="json")
    lst.client.patch(f"{links}{a['id']}/", {"destination_url": "https://b.example/"}, format="json")
    lst.client.delete(f"{links}{b['id']}/")
    lst.add("x", destination_url="https://a.example/")  # a new link reusing a's old URL

    assert lst.restore(3).status_code == 200
    urls = {link["id"]: link["destination_url"] for link in lst.links()}
    assert urls == {a["id"]: "https://a.example/", b["id"]: "https://b.example/"}


def test_who_may_restore(alice, bob):
    lst = Lst(client_for(alice))
    lst.add("a")
    shared_list = SharedList.objects.get(public_code=lst.code)
    ListMembership.objects.create(shared_list=shared_list, user=bob, role="viewer")
    viewer = client_for(bob)
    response = viewer.post(
        f"{URL}{lst.code}/restore/", {"revision": 1}, format="json", HTTP_IF_MATCH='"r2"'
    )
    assert response.status_code == 403
    legacy, token = legacy_services.create_list(title="Legacy")
    legacy_services.add_link(legacy, destination_url="https://a.example/")
    by_token = client_for(HTTP_AUTHORIZATION=f"Bearer {token}").post(
        f"{URL}{legacy.public_code}/restore/", {"revision": 1}, format="json", HTTP_IF_MATCH='"r2"'
    )
    assert by_token.status_code == 200 and by_token.json()["changed"] is True
    newest = ListRevision.objects.filter(shared_list=legacy).order_by("-number").first()
    assert newest.created_by is None and newest.kind == "restored"
