"""Revisions in PostgreSQL (task 3.1; docs/v2/07-REVISION-SPEC.md): numbering, no-ops,
immutability, cascades, concurrency, and the baseline migration for existing lists."""

import threading
from datetime import timedelta

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from apps.accounts.models import DELETION_GRACE, User
from apps.accounts.services import delete_account, purge_deleted_accounts
from apps.sharing import services as legacy_services
from apps.sharing.models import SharedLink, SharedList
from apps.sharing.selectors import Principal, live_content
from apps.sharing.services import links as link_services
from apps.sharing.services import lists as list_services
from apps.versioning.domain import snapshot
from apps.versioning.models import ListRevision, RevisionKind
from apps.versioning.services import head_snapshot, record_revision


def make_user(email="alice@example.com"):
    return User.objects.create_user(email, "pw-correct-horse-1")


def new_list(owner, title="Tools") -> SharedList:
    shared_list, _ = list_services.create_list(Principal(user=owner), title=title)
    return shared_list


def locked(shared_list) -> SharedList:
    return SharedList.objects.select_for_update().get(pk=shared_list.pk)


def record(shared_list, kind=RevisionKind.EDITED, **kwargs):
    with transaction.atomic():
        return record_revision(locked(shared_list), kind=kind, **kwargs)


@pytest.fixture
def alice(db):
    return make_user()


def test_revisions_are_numbered_and_no_ops_write_nothing(alice):
    shared_list = new_list(alice)
    first = record(shared_list, RevisionKind.CREATED, user=alice)
    assert (first.number, first.kind, first.created_by) == (1, "created", alice)
    assert first.summary == {"added": 0, "removed": 0, "modified": 0, "moved": 0, "list": []}
    assert record(shared_list) is None  # nothing changed
    link_services.add_link_on(shared_list, destination_url="https://example.com/a", title="A")

    second = record(shared_list, user=alice)
    assert second.number == 2 and second.summary["added"] == 1
    assert second.snapshot["links"][0]["title"] == "A"
    shared_list.refresh_from_db()
    assert shared_list.head_revision == 2
    assert head_snapshot(shared_list) == second.snapshot


def test_settings_and_fetched_metadata_are_not_content(alice):
    shared_list = new_list(alice)
    link = link_services.add_link_on(shared_list, destination_url="https://example.com/a")
    record(shared_list, RevisionKind.CREATED)
    SharedList.objects.filter(pk=shared_list.pk).update(visibility="public", image="images/x.webp")
    SharedLink.objects.filter(pk=link.pk).update(metadata={"title": "Fetched"})
    assert record(shared_list) is None


@pytest.mark.django_db(transaction=True)  # no test-wide transaction around this one
def test_recording_needs_the_mutations_transaction():
    with pytest.raises(RuntimeError, match="transaction"):
        record_revision(new_list(make_user()), kind=RevisionKind.EDITED)


def test_revisions_are_immutable(alice):
    revision = record(new_list(alice), RevisionKind.CREATED)
    with pytest.raises(TypeError, match="immutable"):
        revision.save()
    # The trigger raises restrict_violation, which psycopg reports as an IntegrityError.
    with pytest.raises(IntegrityError, match="immutable"), transaction.atomic():
        ListRevision.objects.filter(pk=revision.pk).update(kind="edited")
    with pytest.raises(IntegrityError, match="immutable"), transaction.atomic():
        ListRevision.objects.filter(pk=revision.pk).update(created_by=alice)
    with pytest.raises(IntegrityError, match="immutable"), transaction.atomic():
        ListRevision.objects.filter(pk=revision.pk).update(created_by=None)  # no exceptions


def test_numbers_are_unique_per_list(alice):
    shared_list = new_list(alice)
    revision = record(shared_list, RevisionKind.CREATED)
    with pytest.raises(IntegrityError), transaction.atomic():
        ListRevision.objects.create(
            shared_list=shared_list,
            number=1,
            schema_version=1,
            kind="edited",
            snapshot=revision.snapshot,
        )


def test_deleting_a_list_deletes_its_history(alice):
    shared_list = new_list(alice)
    record(shared_list, RevisionKind.CREATED)
    list_services.delete_list(Principal(user=alice), shared_list.pk)
    assert not ListRevision.objects.exists()


def test_an_erased_author_still_owns_their_revisions(alice):
    """Erasing an account keeps an anonymous user row (ADR-016), so the revisions it wrote on
    other people's lists keep their author and are never changed."""
    bob = make_user("bob@example.com")
    shared_list = new_list(alice)
    revision = record(shared_list, RevisionKind.CREATED, user=bob)
    delete_account(bob, confirm=bob.email)
    User.objects.filter(pk=bob.pk).update(deleted_at=timezone.now() - DELETION_GRACE * 2)
    assert purge_deleted_accounts() == 1

    kept = ListRevision.objects.get(pk=revision.pk)
    assert kept.created_by_id == bob.pk and kept.snapshot == revision.snapshot
    assert kept.created_by.is_active is False and kept.created_by.display_name == ""


def test_legacy_lists_are_versioned_too(db):
    shared_list, _ = legacy_services.create_list(title="Legacy")
    legacy_services.add_link(shared_list, destination_url="https://example.com/a")
    revision = record(shared_list, RevisionKind.CREATED)  # an edit link: no user
    assert revision.created_by is None and len(revision.snapshot["links"]) == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_writers_get_consecutive_numbers():
    owner = make_user()
    shared_list = new_list(owner)
    record(shared_list, RevisionKind.CREATED)
    writers = 20
    barrier = threading.Barrier(writers)
    errors = []

    def write(i):
        try:
            barrier.wait()
            with transaction.atomic():
                row = locked(shared_list)
                link_services.add_link_on(row, destination_url=f"https://example.com/{i}")
                record_revision(row, kind=RevisionKind.EDITED)
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
    numbers = list(
        ListRevision.objects.filter(shared_list=shared_list)
        .order_by("number")
        .values_list("number", flat=True)
    )
    assert numbers == list(range(1, writers + 2))  # no gaps, no duplicates
    shared_list.refresh_from_db()
    assert shared_list.head_revision == writers + 1
    assert head_snapshot(shared_list) == snapshot.build(**live_content(shared_list))  # R4


BEFORE = [("sharing", "0007_head_revision"), ("versioning", "0002_revision_immutable_trigger")]
AFTER = [("versioning", "0003_baseline_revisions")]


@pytest.mark.django_db(transaction=True)
def test_the_migration_gives_existing_lists_a_baseline_revision():
    executor = MigrationExecutor(connection)
    executor.migrate(BEFORE)
    state = executor.loader.project_state(BEFORE).apps
    OldList = state.get_model("sharing", "SharedList")
    OldLink = state.get_model("sharing", "SharedLink")
    now = timezone.now()
    lists = []
    for i, (title, description) in enumerate([("Has links", "About"), ("Empty", "")]):
        lists.append(
            OldList.objects.create(
                public_code=f"Baseline{i:08d}",
                owner_token_hash=str(i) * 64,
                title=title,
                description=description,
                visibility="unlisted",
                expires_at=now + timedelta(days=5),
            )
        )
    first = lists[0]
    OldLink.objects.create(
        shared_list=first, destination_url="https://example.com/b", title="", position=1
    )
    OldLink.objects.create(
        shared_list=first,
        destination_url="https://example.com/a",
        title="A",
        description="Notes",
        icon="icons/ab/ab.webp",
        position=0,
    )
    OldLink.objects.create(
        shared_list=first,
        destination_url="https://example.com/gone",
        deleted_at=now,
        position=None,
    )

    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(AFTER)
    for old in lists:
        shared_list = SharedList.objects.get(pk=old.pk)
        revision = ListRevision.objects.get(shared_list=shared_list)
        assert (revision.number, revision.kind, revision.created_by_id) == (1, "migrated", None)
        assert shared_list.head_revision == 1
        assert revision.snapshot == snapshot.build(**live_content(shared_list))
    baseline = ListRevision.objects.get(shared_list_id=first.pk).snapshot
    assert [link["url"] for link in baseline["links"]] == [
        "https://example.com/a",
        "https://example.com/b",
    ]  # in order, without the deleted link
    assert baseline["links"][1]["title"] is None  # blank titles are null

    # Reversible: the baselines go, and the heads return to 0.
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate([("versioning", "0002_revision_immutable_trigger")])
    assert not ListRevision.objects.exists()
    assert set(SharedList.objects.values_list("head_revision", flat=True)) == {0}

    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes())
