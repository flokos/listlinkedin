"""Every content change writes exactly one revision (task 3.2; docs/v2/07-REVISION-SPEC.md):
R1 one per change and none for no-ops or settings, R2 contiguous numbers under concurrency,
R4 the head equals the live content, plus forced failures and the If-Match precondition."""

import io
import random
import threading

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.sharing.models import SharedLink, SharedList
from apps.sharing.policy import Visibility
from apps.sharing.selectors import Principal, live_content
from apps.sharing.services import links as link_services
from apps.sharing.services import lists as list_services
from apps.versioning.domain import snapshot
from apps.versioning.models import ListRevision
from apps.versioning.services import head_snapshot

URL = "/api/v2/lists/"


@pytest.fixture
def alice(db):
    return User.objects.create_user("alice@example.com", "pw-correct-horse-1")


@pytest.fixture
def client(alice) -> APIClient:
    client = APIClient()
    client.force_authenticate(alice)
    return client


def revisions(shared_list) -> list[tuple[int, str]]:
    return list(
        ListRevision.objects.filter(shared_list=shared_list)
        .order_by("number")
        .values_list("number", "kind")
    )


def head_matches_live(shared_list) -> bool:
    shared_list.refresh_from_db()
    return head_snapshot(shared_list) == snapshot.build(**live_content(shared_list))


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (8, 8), (1, 2, 3)).save(out, format="PNG")
    return out.getvalue()


def test_each_v2_change_writes_one_revision_and_no_ops_none(client, alice):
    created = client.post(URL, {"title": "Tools"}, format="json").json()
    code = created["code"]
    shared_list = SharedList.objects.get(public_code=code)
    links = f"{URL}{code}/links/"
    assert revisions(shared_list) == [(1, "created")]
    assert created["head_revision"] == 1

    steps = [
        # (request, revisions written)
        (lambda: client.patch(f"{URL}{code}/", {"title": "Dev tools"}, format="json"), 1),
        (lambda: client.patch(f"{URL}{code}/", {"title": "Dev tools"}, format="json"), 0),
        (lambda: client.patch(f"{URL}{code}/", {"visibility": "unlisted"}, format="json"), 0),
        (lambda: client.patch(f"{URL}{code}/", {"expires_at": None}, format="json"), 0),
        (lambda: client.post(links, {"destination_url": "https://a.example/"}, format="json"), 1),
        (lambda: client.post(links, {"destination_url": "https://b.example/"}, format="json"), 1),
    ]
    for request, written in steps:
        before = len(revisions(shared_list))
        assert request().status_code in (200, 201)
        assert len(revisions(shared_list)) == before + written
        assert head_matches_live(shared_list)

    a, b = (
        link.pk for link in SharedLink.objects.filter(shared_list=shared_list).order_by("position")
    )
    more = [
        (lambda: client.patch(f"{links}{a}/", {"title": "A"}, format="json"), 1),
        (lambda: client.patch(f"{links}{a}/", {"title": "A"}, format="json"), 0),
        (
            lambda: client.post(
                f"{URL}{code}/reorder/", {"link": str(b), "to_index": 0}, format="json"
            ),
            1,
        ),
        (
            lambda: client.post(
                f"{URL}{code}/reorder/", {"link": str(b), "to_index": 0}, format="json"
            ),
            0,
        ),
        (
            lambda: client.put(
                f"{links}{a}/icon/",
                {"file": SimpleUploadedFile("i.png", png())},
                format="multipart",
            ),
            1,  # the uploaded icon is content
        ),
        (
            lambda: client.put(
                f"{URL}{code}/image/",
                {"file": SimpleUploadedFile("i.png", png())},
                format="multipart",
            ),
            0,  # the list image is a setting
        ),
        (lambda: client.delete(f"{links}{a}/"), 1),
    ]
    for request, written in more:
        before = len(revisions(shared_list))
        assert request().status_code in (200, 201, 204)
        assert len(revisions(shared_list)) == before + written
        assert head_matches_live(shared_list)

    numbers = [n for n, _ in revisions(shared_list)]
    assert numbers == list(range(1, len(numbers) + 1))  # R2: contiguous
    assert {kind for _, kind in revisions(shared_list)[1:]} == {"edited"}
    assert set(ListRevision.objects.values_list("created_by", flat=True)) == {alice.pk}


def test_moving_to_another_list_writes_one_revision_in_each(client):
    source = client.post(URL, {"title": "Inbox"}, format="json").json()["code"]
    target = client.post(URL, {"title": "Archive"}, format="json").json()["code"]
    link = client.post(
        f"{URL}{source}/links/", {"destination_url": "https://a.example/"}, format="json"
    ).json()
    response = client.post(
        f"{URL}{source}/links/{link['id']}/move-to-list/", {"list": target}, format="json"
    )
    assert response.status_code == 201
    for code, expected in (
        (source, [(1, "created"), (2, "edited"), (3, "edited")]),
        (target, [(1, "created"), (2, "edited")]),
    ):
        shared_list = SharedList.objects.get(public_code=code)
        assert revisions(shared_list) == expected
        assert head_matches_live(shared_list)


def test_fetched_metadata_never_writes_a_revision(client):
    code = client.post(URL, {"title": "Tools"}, format="json").json()["code"]
    client.post(f"{URL}{code}/links/", {"destination_url": "https://a.example/"}, format="json")
    shared_list = SharedList.objects.get(public_code=code)
    SharedLink.objects.filter(shared_list=shared_list).update(metadata={"title": "Fetched"})
    client.patch(f"{URL}{code}/", {"visibility": "unlisted"}, format="json")
    assert len(revisions(shared_list)) == 2
    assert head_matches_live(shared_list)


def test_a_failure_while_versioning_rolls_back_the_change(alice, monkeypatch):
    """R1: the change and its revision commit together or not at all."""
    shared_list, _ = list_services.create_list(Principal(user=alice), title="Tools")

    def broken(*args, **kwargs):
        raise RuntimeError("simulated failure after the link write, before commit")

    monkeypatch.setattr("apps.versioning.services.diff.summarize", broken)
    with pytest.raises(RuntimeError, match="simulated"):
        link_services.add_link(
            Principal(user=alice), shared_list.pk, destination_url="https://a.example/"
        )
    assert not SharedLink.objects.filter(shared_list=shared_list).exists()
    assert revisions(shared_list) == [(1, "created")]
    shared_list.refresh_from_db()
    assert shared_list.head_revision == 1


@pytest.mark.django_db(transaction=True)
def test_twenty_concurrent_edits_get_revisions_2_to_21():
    owner = User.objects.create_user("owner@example.com", "pw-correct-horse-1")
    principal = Principal(user=owner)
    shared_list, _ = list_services.create_list(principal, title="Race")
    writers = 20
    barrier = threading.Barrier(writers)
    errors = []

    def write(i):
        try:
            barrier.wait()
            link_services.add_link(
                principal, shared_list.pk, destination_url=f"https://example.com/{i}"
            )
        except Exception as exc:  # noqa: BLE001 - reported below
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=write, args=(i,)) for i in range(writers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert [n for n, _ in revisions(shared_list)] == list(range(1, writers + 2))
    assert head_matches_live(shared_list)
    head = ListRevision.objects.get(shared_list=shared_list, number=writers + 1)
    assert len(head.snapshot["links"]) == writers


@pytest.mark.parametrize("seed", range(5))
def test_the_head_always_equals_the_live_content(alice, seed):
    """R4 over random sequences of every content operation (seeded, so failures reproduce)."""
    rng = random.Random(seed)
    principal = Principal(user=alice)
    shared_list, _ = list_services.create_list(principal, title="Random")
    for step in range(40):
        live = list(SharedLink.objects.filter(shared_list=shared_list, deleted_at__isnull=True))
        operation = rng.choice(["add", "add", "edit", "delete", "move", "rename", "noop"])
        if operation == "add" or not live:
            link_services.add_link(
                principal,
                shared_list.pk,
                destination_url=f"https://example.com/{seed}/{step}",
                title=rng.choice([None, f"T{step}"]),
                position=rng.choice([None, 0, rng.randrange(len(live) + 1)]),
            )
        elif operation == "edit":
            link_services.update_link(
                principal, shared_list.pk, rng.choice(live).pk, {"title": rng.choice(["x", "y"])}
            )
        elif operation == "delete":
            link_services.delete_link(principal, shared_list.pk, rng.choice(live).pk)
        elif operation == "move":
            link_services.move_link(
                principal, shared_list.pk, rng.choice(live).pk, rng.randrange(len(live))
            )
        elif operation == "rename":
            list_services.update_list(principal, shared_list.pk, {"title": rng.choice(["A", "B"])})
        else:
            list_services.update_list(
                principal, shared_list.pk, {"visibility": Visibility.UNLISTED}
            )
        assert head_matches_live(shared_list), (seed, step, operation)
    numbers = [n for n, _ in revisions(shared_list)]
    assert numbers == list(range(1, len(numbers) + 1))


def test_etags_and_the_if_match_precondition(client):
    code = client.post(URL, {"title": "Tools"}, format="json").json()["code"]
    detail = client.get(f"{URL}{code}/")
    assert detail["ETag"] == '"r1"' and detail.json()["head_revision"] == 1
    assert client.get(f"{URL}{code}/links/")["ETag"] == '"r1"'

    added = client.post(
        f"{URL}{code}/links/",
        {"destination_url": "https://a.example/"},
        format="json",
        HTTP_IF_MATCH='"r1"',
    )
    assert added.status_code == 201 and added["ETag"] == '"r2"'

    stale = client.patch(f"{URL}{code}/", {"title": "New"}, format="json", HTTP_IF_MATCH='"r1"')
    assert stale.status_code == 412
    assert stale.json()["code"] == "revision_mismatch" and stale.json()["head_revision"] == 2
    assert client.get(f"{URL}{code}/").json()["title"] == "Tools"  # nothing changed

    current = client.get(f"{URL}{code}/")["ETag"]
    ok = client.patch(f"{URL}{code}/", {"title": "New"}, format="json", HTTP_IF_MATCH=current)
    assert ok.status_code == 200 and ok["ETag"] == '"r3"'
    anything = client.patch(f"{URL}{code}/", {"title": "Any"}, format="json", HTTP_IF_MATCH="*")
    assert anything.status_code == 200
    for value in ('W/"r4"', "banana"):  # weak or foreign ETags never match
        refused = client.patch(f"{URL}{code}/", {"title": "X"}, format="json", HTTP_IF_MATCH=value)
        assert refused.status_code == 412, value
    # Settings aren't content: an old ETag doesn't stop a visibility change.
    settings = client.patch(
        f"{URL}{code}/", {"visibility": "unlisted"}, format="json", HTTP_IF_MATCH='"r1"'
    )
    assert settings.status_code == 200

    link_id = added.json()["id"]
    assert client.delete(f"{URL}{code}/links/{link_id}/", HTTP_IF_MATCH='"r1"').status_code == 412
    assert SharedLink.objects.get(pk=link_id).deleted_at is None
