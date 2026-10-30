"""POST /api/v2/lists/{code}/fork/: "Make a copy" (docs/v2/08 Fork vs branch)."""

import io
import threading
import uuid

import pytest
from django.db import connection
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.sharing.models import ListMembership, SharedLink, SharedList
from apps.sharing.policy import Visibility
from apps.sharing.selectors import Principal
from apps.sharing.services import forks as fork_services
from apps.sharing.services import links as link_services
from apps.sharing.services import lists as list_services
from apps.sharing.services import media as media_services
from apps.shortener.models import ShortRedirect
from apps.versioning.models import ListRevision
from apps.versioning.services import head_snapshot

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


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (64, 64), (20, 120, 220)).save(out, format="PNG")
    return out.getvalue()


def make_source(owner, *, visibility=Visibility.PRIVATE, allow_fork=False, links=3):
    principal = Principal(user=owner)
    source, _ = list_services.create_list(
        principal,
        title="Dev tools",
        description="Things we use",
        visibility=visibility,
        allow_fork=allow_fork,
    )
    for i in range(links):
        link_services.add_link(
            principal, source.pk, destination_url=f"https://example.com/{i}", title=f"Tool {i}"
        )
    source.refresh_from_db()
    return source


def fork(user, source, **data):
    return client_for(user).post(f"{URL}{source.public_code}/fork/", data, format="json")


def short_codes(shared_list) -> set[str]:
    return set(
        ShortRedirect.objects.filter(link__shared_list=shared_list).values_list("code", flat=True)
    )


def test_a_copy_is_a_new_private_list_with_the_same_content(alice):
    source = make_source(alice, visibility=Visibility.UNLISTED, allow_fork=True)
    first = source.links.get(position=0)
    first.metadata = {"title": "Fetched"}
    first.metadata_fetched_at = timezone.now()
    first.save(update_fields=["metadata", "metadata_fetched_at"])
    media_services.set_list_image(Principal(user=alice), source.pk, png())
    media_services.set_link_icon(Principal(user=alice), source.pk, first.pk, png())
    source.refresh_from_db()

    response = fork(alice, source)

    assert response.status_code == 201, response.content
    data = response.json()
    assert data["title"] == "Dev tools (copy)"
    assert data["slug"] == "dev-tools-copy"
    assert data["description"] == "Things we use"
    assert data["image_url"] is not None
    assert (data["visibility"], data["allow_fork"], data["expires_at"]) == ("private", False, None)
    assert data["my_role"] == "owner"
    assert data["head_revision"] == 1 and data["link_count"] == 3
    assert data["origin"] == {
        "kind": "fork",
        "parent": {"code": source.public_code, "title": "Dev tools"},
    }

    copy = SharedList.objects.get(public_code=data["code"])
    assert copy.owner == alice and copy.forked_from_id == source.pk
    assert copy.image == source.image
    originals = list(source.links.order_by("position"))
    copies = list(copy.links.order_by("position"))
    assert [c.source_link_id for c in copies] == [o.pk for o in originals]
    assert {c.pk for c in copies}.isdisjoint({o.pk for o in originals})
    assert [(c.destination_url, c.title, c.position) for c in copies] == [
        (o.destination_url, o.title, o.position) for o in originals
    ]
    assert copies[0].icon == originals[0].icon is not None
    assert copies[0].metadata == {"title": "Fetched"} and copies[0].metadata_fetched_at
    # New short URLs, one per link.
    assert len(short_codes(copy)) == 3 and short_codes(copy).isdisjoint(short_codes(source))
    # Revision 1 is `forked`, by the person who made the copy, and equals the live content.
    revision = ListRevision.objects.get(shared_list=copy)
    assert (revision.number, revision.kind, revision.created_by) == (1, "forked", alice)
    assert [link["source_link_id"] for link in revision.snapshot["links"]] == [
        str(o.pk) for o in originals
    ]


def test_a_copy_can_have_its_own_title(alice):
    source = make_source(alice, links=0)
    response = fork(alice, source, title="Mine")
    assert response.status_code == 201
    assert response.json()["title"] == "Mine"
    assert fork(alice, source, title="").status_code == 400


def test_a_long_title_still_fits_with_the_suffix():
    assert len(fork_services.copy_title("x" * 255)) == 255
    assert fork_services.copy_title("x" * 255).endswith(" (copy)")


def test_who_may_make_a_copy(alice, bob):
    """The owner always; others only if they can view the list and copies are allowed."""
    private = make_source(alice, links=0)
    unlisted = make_source(alice, visibility=Visibility.UNLISTED, links=0)
    allowed = make_source(alice, visibility=Visibility.UNLISTED, allow_fork=True, links=0)

    assert fork(alice, private).status_code == 201
    assert fork(None, allowed).status_code == 401
    assert fork(bob, private).status_code == 404  # private lists don't reveal they exist
    assert fork(bob, unlisted).status_code == 403
    assert fork(bob, unlisted).json()["code"] == "permission_denied"
    assert fork(bob, allowed).status_code == 201

    # A member of a private list needs allow_fork too, whatever their role.
    ListMembership.objects.create(shared_list=private, user=bob, role="editor")
    assert fork(bob, private).status_code == 403
    SharedList.objects.filter(pk=private.pk).update(allow_fork=True)
    assert fork(bob, private).status_code == 201
    copy = SharedList.objects.get(forked_from_id=private.pk, owner=bob)
    # Roles never carry over to the copy.
    assert not ListMembership.objects.filter(shared_list=copy).exists()


def test_permissions_include_fork_only_when_allowed(alice, bob):
    source = make_source(alice, visibility=Visibility.UNLISTED, links=0)
    detail = client_for(bob).get(f"{URL}{source.public_code}/").json()
    assert "fork" not in detail["permissions"]
    SharedList.objects.filter(pk=source.pk).update(allow_fork=True)
    detail = client_for(bob).get(f"{URL}{source.public_code}/").json()
    assert "fork" in detail["permissions"]
    assert "fork" in client_for(alice).get(f"{URL}{source.public_code}/").json()["permissions"]


def test_legacy_and_expired_lists_cant_be_copied(alice, bob, owned_list, expire):
    legacy, token = owned_list
    response = client_for().post(
        f"{URL}{legacy.public_code}/fork/", {}, format="json", HTTP_AUTHORIZATION=f"Bearer {token}"
    )
    assert response.status_code == 401  # an edit link isn't an account
    assert fork(bob, legacy).status_code == 403  # legacy lists never allow copies

    source = make_source(alice, links=0)
    expire(source)
    assert fork(alice, source).status_code == 410


def test_a_copy_is_independent_of_its_source(alice, bob):
    source = make_source(alice, visibility=Visibility.UNLISTED, allow_fork=True)
    copy_code = fork(bob, source).json()["code"]
    copy = SharedList.objects.get(public_code=copy_code)

    link_services.add_link(Principal(user=alice), source.pk, destination_url="https://new.example/")
    list_services.update_list(Principal(user=alice), source.pk, {"title": "Renamed"})
    assert copy.links.count() == 3
    assert client_for(bob).get(f"{URL}{copy_code}/").json()["origin"]["parent"]["title"] == (
        "Renamed"
    )
    # The copy is private: its short URLs don't work for others.
    code = next(iter(short_codes(copy)))
    assert client_for().get(f"/r/{code}").status_code == 404
    session = APIClient()
    session.force_login(bob)
    assert session.get(f"/r/{code}").status_code == 302

    # Once the source can't be viewed, or is gone, the copy doesn't name it.
    list_services.update_list(Principal(user=alice), source.pk, {"visibility": "private"})
    assert client_for(bob).get(f"{URL}{copy_code}/").json()["origin"] == {
        "kind": "fork",
        "parent": None,
    }
    list_services.delete_list(Principal(user=alice), source.pk)
    data = client_for(bob).get(f"{URL}{copy_code}/").json()
    assert data["origin"] == {"kind": "fork", "parent": None}
    assert data["link_count"] == 3


def test_my_lists_show_origins_without_extra_queries_per_list(
    alice, bob, django_assert_max_num_queries
):
    source = make_source(alice, visibility=Visibility.UNLISTED, allow_fork=True, links=0)
    for _ in range(5):
        fork(bob, source)
    with django_assert_max_num_queries(8):
        page = client_for(bob).get(URL).json()["results"]
    assert len(page) == 5
    assert {lst["origin"]["parent"]["code"] for lst in page} == {source.public_code}
    assert client_for(alice).get(f"{URL}{source.public_code}/").json()["origin"] is None


def test_the_copy_is_made_from_the_head_revision(alice):
    """A link whose URL changed outside a revision (a concurrent write between the snapshot
    and the copy) is copied as the snapshot has it, without the other URL's metadata."""
    source = make_source(alice, links=1)
    SharedLink.objects.filter(shared_list=source).update(
        destination_url="https://elsewhere.example/", metadata={"title": "Elsewhere"}
    )
    copy, created = fork_services.fork_list(Principal(user=alice), source.public_code)
    link = copy.links.get()
    assert created
    assert link.destination_url == "https://example.com/0"
    assert link.metadata == {}
    assert head_snapshot(copy)["links"][0]["url"] == "https://example.com/0"


def test_idempotency_key_returns_the_first_copy(alice, bob):
    source = make_source(alice, visibility=Visibility.UNLISTED, allow_fork=True, links=1)
    other = make_source(alice, visibility=Visibility.UNLISTED, allow_fork=True, links=0)
    key = str(uuid.uuid4())

    def post(user, lst):
        return client_for(user).post(
            f"{URL}{lst.public_code}/fork/", {}, format="json", HTTP_IDEMPOTENCY_KEY=key
        )

    first, again = post(bob, source), post(bob, source)
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json()["id"] == first.json()["id"]
    assert post(bob, other).json()["code"] == "idempotency_key_reused"
    assert post(alice, source).status_code == 409  # someone else's key
    assert SharedList.objects.filter(forked_from_id__isnull=False).count() == 1


def test_a_failure_leaves_nothing_behind(alice, monkeypatch):
    source = make_source(alice, links=3)
    lists, links, redirects = (
        SharedList.objects.count(),
        SharedLink.objects.count(),
        ShortRedirect.objects.count(),
    )

    def broken(*args, **kwargs):
        raise RuntimeError("simulated failure after the links were copied")

    monkeypatch.setattr("apps.versioning.services.diff.summarize", broken)
    with pytest.raises(RuntimeError, match="simulated"):
        fork_services.fork_list(Principal(user=alice), source.public_code)
    assert SharedList.objects.count() == lists
    assert SharedLink.objects.count() == links
    assert ShortRedirect.objects.count() == redirects


def test_a_full_list_can_be_copied(alice):
    source = make_source(alice, links=0)
    principal = Principal(user=alice)
    for i in range(100):
        link_services.add_link(principal, source.pk, destination_url=f"https://example.com/{i}")
    copy, _ = fork_services.fork_list(principal, source.public_code)
    assert copy.links.count() == 100
    assert len(short_codes(copy)) == 100


@pytest.mark.django_db(transaction=True)
def test_concurrent_retries_with_one_key_make_one_copy():
    owner = User.objects.create_user("owner@example.com", "pw-correct-horse-1")
    source = make_source(owner, links=2)
    key = uuid.uuid4()
    workers = 8
    barrier = threading.Barrier(workers)
    results, failures = [], []

    def run():
        try:
            barrier.wait()
            results.append(
                fork_services.fork_list(Principal(user=owner), source.public_code, creation_key=key)
            )
        except Exception as exc:  # noqa: BLE001 - reported below
            failures.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=run) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert failures == []
    assert len({copy.pk for copy, _ in results}) == 1
    assert sum(created for _, created in results) == 1
    copy = SharedList.objects.get(forked_from_id=source.pk)
    assert copy.links.count() == 2


@pytest.mark.django_db(transaction=True)
def test_copies_made_during_edits_match_a_revision_of_the_source():
    """The source isn't locked: a copy made while it changes is exactly one of its revisions."""
    owner = User.objects.create_user("owner@example.com", "pw-correct-horse-1")
    principal = Principal(user=owner)
    source = make_source(owner, links=0)
    rounds = 10
    barrier = threading.Barrier(2)
    failures = []

    def edit():
        try:
            barrier.wait()
            for i in range(rounds):
                link_services.add_link(
                    principal, source.pk, destination_url=f"https://example.com/{i}"
                )
        except Exception as exc:  # noqa: BLE001 - reported below
            failures.append(exc)
        finally:
            connection.close()

    def copy():
        try:
            barrier.wait()
            for _ in range(rounds):
                fork_services.fork_list(principal, source.public_code)
        except Exception as exc:  # noqa: BLE001 - reported below
            failures.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=edit), threading.Thread(target=copy)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert failures == []
    source_urls = [
        [link["url"] for link in r.snapshot["links"]]
        for r in ListRevision.objects.filter(shared_list=source)
    ]
    for copy in SharedList.objects.filter(forked_from_id=source.pk):
        urls = list(copy.links.order_by("position").values_list("destination_url", flat=True))
        assert urls in source_urls


def test_v1_reads_dont_show_copies(alice):
    """A copy is a private account list: the V1 API (no sign-in) answers 404 for it."""
    source = make_source(alice, visibility=Visibility.UNLISTED, allow_fork=True, links=0)
    copy, _ = fork_services.fork_list(Principal(user=alice), source.public_code)
    assert client_for().get(f"/api/v1/lists/{copy.public_code}/").status_code == 404
