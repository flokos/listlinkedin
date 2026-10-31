"""Fetched metadata on links (task 7.3, docs/v2/adr/ADR-008): when fetches are queued, the
task storing results only for the URL they describe, what the API shows, refreshing, and the
backfill command. The fetcher itself is tested in apps/metadata/tests."""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone
from django_tasks_db.models import DBTaskResult
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.metadata import extraction, fetcher
from apps.metadata.tasks import TemporaryFailure
from apps.sharing.models import ListMembership, SharedLink, SharedList
from apps.sharing.policy import Visibility
from apps.sharing.selectors import Principal, media_in_use
from apps.sharing.services import forks as fork_services
from apps.sharing.services import links as link_services
from apps.sharing.services import lists as list_services
from apps.sharing.services import metadata
from apps.versioning.models import ListRevision

URL = "/api/v2/lists/"
FOUND = {
    "title": "Fetched title",
    "description": "Fetched description",
    "site_name": "Example",
    "icon": "icons/ab/abc.webp",
    "image": "images/cd/cde.webp",
    "url": "https://example.com/final",
}


@pytest.fixture
def alice(db):
    return User.objects.create_user("alice@example.com", "pw-correct-horse-1")


@pytest.fixture
def client(alice) -> APIClient:
    client = APIClient()
    client.force_authenticate(alice)
    return client


@pytest.fixture
def shared_list(alice) -> SharedList:
    return list_services.create_list(Principal(user=alice), title="Tools")[0]


def queued() -> list[tuple[str, str]]:
    """The metadata fetches waiting in the queue, as (link id, url)."""
    return [
        tuple(r.args_kwargs["args"])
        for r in DBTaskResult.objects.filter(task_path__endswith="fetch_link_metadata").order_by(
            "enqueued_at"
        )
    ]


def run_worker():
    call_command("db_worker", "--batch", "--no-startup-delay", "--no-reload", verbosity=0)


def add_link(alice, shared_list, url="https://example.com/", **fields) -> SharedLink:
    link, _ = link_services.add_link(
        Principal(user=alice), shared_list.pk, destination_url=url, **fields
    )
    return link


def links_of(client, shared_list):
    return client.get(f"{URL}{shared_list.public_code}/links/").json()["results"]


# When fetches are queued.


def test_new_links_and_url_changes_queue_a_fetch_on_commit(
    alice, shared_list, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        link = add_link(alice, shared_list)
        assert queued() == []  # not before the commit
    assert queued() == [(str(link.pk), "https://example.com/")]

    with django_capture_on_commit_callbacks(execute=True):
        link_services.update_link(Principal(user=alice), shared_list.pk, link.pk, {"title": "x"})
    assert len(queued()) == 1  # a title edit fetches nothing

    with django_capture_on_commit_callbacks(execute=True):
        link_services.update_link(
            Principal(user=alice),
            shared_list.pk,
            link.pk,
            {"destination_url": "https://example.org/"},
        )
    assert queued()[-1] == (str(link.pk), "https://example.org/")


def test_nothing_is_queued_while_fetching_is_off(
    alice, shared_list, settings, django_capture_on_commit_callbacks
):
    settings.METADATA_FETCH_ENABLED = False
    with django_capture_on_commit_callbacks(execute=True):
        add_link(alice, shared_list)
    assert queued() == []


def test_copies_bring_their_metadata_and_fetch_only_what_is_missing(
    alice, shared_list, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        fetched = add_link(alice, shared_list, "https://example.com/a")
        bare = add_link(alice, shared_list, "https://example.com/b")
    metadata.store(str(fetched.pk), fetched.destination_url, FOUND)
    other, _ = list_services.create_list(Principal(user=alice), title="Other")
    DBTaskResult.objects.all().delete()

    with django_capture_on_commit_callbacks(execute=True):
        moved = link_services.move_link_to_list(
            Principal(user=alice), shared_list.pk, fetched.pk, other.pk
        )
    assert moved.metadata["title"] == "Fetched title"
    assert queued() == []  # moved with its metadata: nothing to fetch

    SharedList.objects.filter(pk=shared_list.pk).update(allow_fork=True)
    with django_capture_on_commit_callbacks(execute=True):
        copy, _ = fork_services.fork_list(Principal(user=alice), shared_list.public_code)
    (copied,) = copy.links.all()
    assert copied.destination_url == bare.destination_url
    assert queued() == [(str(copied.pk), bare.destination_url)]  # it had nothing to copy


def test_a_restore_that_changes_a_url_queues_a_fetch(
    alice, shared_list, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        link = add_link(alice, shared_list, "https://example.com/old")
    metadata.store(str(link.pk), link.destination_url, FOUND)
    principal = Principal(user=alice)
    link_services.update_link(
        principal, shared_list.pk, link.pk, {"destination_url": "https://example.com/new"}
    )
    metadata.store(str(link.pk), "https://example.com/new", FOUND)  # the worker caught up
    shared_list.refresh_from_db()
    DBTaskResult.objects.all().delete()
    from apps.sharing.services import restore

    with django_capture_on_commit_callbacks(execute=True):
        restore.restore_revision(
            principal, shared_list.pk, 2, expected_head=shared_list.head_revision
        )
    # Back to the old URL, whose metadata the row no longer holds.
    assert queued() == [(str(link.pk), "https://example.com/old")]


# The task.


@pytest.mark.django_db(transaction=True)
def test_the_worker_stores_metadata_without_touching_the_link(monkeypatch):
    alice = User.objects.create_user("w@example.com", "pw-correct-horse-1")
    shared_list = list_services.create_list(Principal(user=alice), title="Tools")[0]
    link = add_link(alice, shared_list, title="My own title")
    before = SharedLink.objects.get(pk=link.pk)
    revisions = ListRevision.objects.filter(shared_list=shared_list).count()
    monkeypatch.setattr(extraction, "extract", lambda url: dict(FOUND))

    run_worker()

    after = SharedLink.objects.get(pk=link.pk)
    assert after.metadata == {
        **FOUND,
        "link_url": "https://example.com/",
        "status": "ready",
        "error": None,
    }
    assert after.metadata_fetched_at is not None
    assert (after.title, after.description, after.icon) == ("My own title", None, None)
    assert after.updated_at == before.updated_at  # not content
    assert ListRevision.objects.filter(shared_list=shared_list).count() == revisions
    assert DBTaskResult.objects.get().return_value == "ready"

    client = APIClient()
    client.force_authenticate(alice)
    (shown,) = links_of(client, shared_list)
    assert shown["metadata_status"] == "ready"
    assert shown["display"] == {
        "title": "My own title",  # the user's own value always wins
        "description": "Fetched description",
        "icon_url": "/media/icons/ab/abc.webp",
        "site_name": "Example",
    }
    assert shown["fetched"]["title"] == "Fetched title"


@pytest.mark.django_db(transaction=True)
def test_a_result_for_an_old_url_or_a_deleted_link_is_dropped(monkeypatch):
    alice = User.objects.create_user("w@example.com", "pw-correct-horse-1")
    principal = Principal(user=alice)
    shared_list = list_services.create_list(principal, title="Tools")[0]
    link = add_link(alice, shared_list, "https://example.com/old")
    deleted = add_link(alice, shared_list, "https://example.com/gone")
    DBTaskResult.objects.all().delete()

    def extract_while_the_user_edits(url):
        link_services.update_link(
            principal, shared_list.pk, link.pk, {"destination_url": "https://example.com/new"}
        )
        return dict(FOUND)

    monkeypatch.setattr(extraction, "extract", extract_while_the_user_edits)
    metadata.request_fetch(link.pk, "https://example.com/old")
    run_worker()
    first = DBTaskResult.objects.filter(args_kwargs__args__1="https://example.com/old").get()
    assert first.return_value.endswith("not stored: the link changed meanwhile")
    assert SharedLink.objects.get(pk=link.pk).metadata.get("link_url") != (
        "https://example.com/old"
    )

    link_services.delete_link(principal, shared_list.pk, deleted.pk)
    assert not metadata.still_wanted(str(deleted.pk), deleted.destination_url)
    assert not metadata.store(str(deleted.pk), deleted.destination_url, FOUND)


@pytest.mark.django_db(transaction=True)
def test_failures_are_recorded_retried_and_never_erase_good_values(monkeypatch):
    alice = User.objects.create_user("w@example.com", "pw-correct-horse-1")
    shared_list = list_services.create_list(Principal(user=alice), title="Tools")[0]
    link = add_link(alice, shared_list)

    def refused(url):
        raise fetcher.FetchFailed("404")

    monkeypatch.setattr(extraction, "extract", refused)
    run_worker()
    assert SharedLink.objects.get(pk=link.pk).metadata == {
        "link_url": "https://example.com/",
        "status": "unavailable",
        "error": "failed",
    }

    def temporary(url):
        raise TemporaryFailure("timeout")

    monkeypatch.setattr(extraction, "extract", temporary)
    metadata.request_fetch(link.pk, link.destination_url)
    run_worker()
    retry = DBTaskResult.objects.filter(status="READY").get()
    assert retry.args_kwargs["kwargs"] == {"attempt": 2}

    # A good result, then a refresh that fails: the good values stay.
    assert metadata.store(str(link.pk), link.destination_url, FOUND)
    assert not metadata.store(str(link.pk), link.destination_url, None, error="unreachable")
    assert SharedLink.objects.get(pk=link.pk).metadata["status"] == "ready"


def test_status_and_display_follow_the_current_url(client, alice, shared_list, settings):
    link = add_link(alice, shared_list)
    assert links_of(client, shared_list)[0]["metadata_status"] == "pending"
    assert links_of(client, shared_list)[0]["fetched"] is None

    metadata.store(str(link.pk), link.destination_url, FOUND)
    assert links_of(client, shared_list)[0]["display"]["title"] == "Fetched title"

    # After a URL change, the old page's values are never shown.
    link_services.update_link(
        Principal(user=alice), shared_list.pk, link.pk, {"destination_url": "https://example.org/"}
    )
    (shown,) = links_of(client, shared_list)
    assert shown["metadata_status"] == "pending"
    assert shown["display"]["title"] == "example.org"
    assert shown["display"]["icon_url"] is None

    settings.METADATA_FETCH_ENABLED = False
    assert links_of(client, shared_list)[0]["metadata_status"] == "disabled"
    metadata.store(str(link.pk), "https://example.org/", None, error="refused")
    assert links_of(client, shared_list)[0]["metadata_status"] == "unavailable"


# Refreshing.


def refresh_url(shared_list, link) -> str:
    return f"{URL}{shared_list.public_code}/links/{link.pk}/refresh-metadata/"


def test_editors_refresh_at_most_once_an_hour(
    client, alice, shared_list, django_capture_on_commit_callbacks
):
    link = add_link(alice, shared_list)
    DBTaskResult.objects.all().delete()
    with django_capture_on_commit_callbacks(execute=True):
        assert client.post(refresh_url(shared_list, link)).status_code == 202
    assert queued() == [(str(link.pk), link.destination_url)]

    again = client.post(refresh_url(shared_list, link))
    assert again.status_code == 429
    assert int(again["Retry-After"]) > 0
    assert len(queued()) == 1


def test_who_may_refresh(client, alice, shared_list, settings):
    link = add_link(alice, shared_list)
    viewer = User.objects.create_user("v@example.com", "pw-correct-horse-2")
    ListMembership.objects.create(shared_list=shared_list, user=viewer, role="viewer")
    as_viewer = APIClient()
    as_viewer.force_authenticate(viewer)
    assert as_viewer.post(refresh_url(shared_list, link)).status_code == 403

    list_services.update_list(
        Principal(user=alice), shared_list.pk, {"visibility": Visibility.UNLISTED}
    )
    assert APIClient().post(refresh_url(shared_list, link)).status_code == 401

    link_services.delete_link(Principal(user=alice), shared_list.pk, link.pk)
    assert client.post(refresh_url(shared_list, link)).status_code == 404

    live = add_link(alice, shared_list, "https://example.com/live")
    settings.METADATA_FETCH_ENABLED = False
    off = client.post(refresh_url(shared_list, live))
    assert (off.status_code, off.json()["code"]) == (409, "metadata_disabled")


# Backfill and media.


def test_backfill_queues_links_without_current_metadata(
    alice, shared_list, settings, capsys, django_capture_on_commit_callbacks
):
    settings.METADATA_FETCH_ENABLED = False  # links made while fetching was off
    fresh = add_link(alice, shared_list, "https://example.com/a")
    done = add_link(alice, shared_list, "https://example.com/b")
    gone = add_link(alice, shared_list, "https://example.com/c")
    metadata.store(str(done.pk), done.destination_url, FOUND)
    link_services.delete_link(Principal(user=alice), shared_list.pk, gone.pk)
    expired = list_services.create_list(Principal(user=alice), title="Old")[0]
    add_link(alice, expired, "https://example.com/expired")
    SharedList.objects.filter(pk=expired.pk).update(expires_at=timezone.now() - timedelta(1))

    call_command("backfill_metadata")
    assert "turned off" in capsys.readouterr().out

    settings.METADATA_FETCH_ENABLED = True
    call_command("backfill_metadata", "--dry-run")
    assert "Would queue 1" in capsys.readouterr().out
    with django_capture_on_commit_callbacks(execute=True):
        call_command("backfill_metadata")
    assert queued() == [(str(fresh.pk), fresh.destination_url)]


def test_fetched_images_count_as_media_in_use(alice, shared_list):
    link = add_link(alice, shared_list)
    metadata.store(str(link.pk), link.destination_url, FOUND)
    assert {"icons/ab/abc.webp", "images/cd/cde.webp"} <= media_in_use()


def test_refreshes_are_also_limited_per_user(client, alice, shared_list, monkeypatch):
    from rest_framework.throttling import ScopedRateThrottle

    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"metadata_refresh": "1/hour"})
    first = add_link(alice, shared_list, "https://example.com/1")
    second = add_link(alice, shared_list, "https://example.com/2")
    assert client.post(refresh_url(shared_list, first)).status_code == 202
    assert client.post(refresh_url(shared_list, second)).status_code == 429  # another link
