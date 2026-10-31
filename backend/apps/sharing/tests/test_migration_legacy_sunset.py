"""sharing.0011 retires lists without an account (task 9.6,
docs/v2/06-MIGRATION-PLAN.md#after-launch-contracting-the-legacy-path)."""

from datetime import timedelta

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

BEFORE = [("sharing", "0010_directory_title_index")]
AFTER = [("sharing", "0012_lists_need_an_owner")]


def legacy_list(code: str, *, expires_in: timedelta):
    executor = MigrationExecutor(connection)
    executor.migrate(BEFORE)
    old = executor.loader.project_state(BEFORE).apps.get_model("sharing", "SharedList")
    return old.objects.create(
        public_code=code,
        owner_token_hash="a" * 64,
        title="Old",
        visibility="unlisted",
        expires_at=timezone.now() + expires_in,
    )


def migrate(target):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(target)
    return executor


def back_to_latest():
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes())


@pytest.mark.django_db(transaction=True)
def test_expired_legacy_lists_are_deleted():
    row = legacy_list("ExpiredLegacy000", expires_in=timedelta(seconds=-1))

    executor = migrate(AFTER)

    new = executor.loader.project_state(AFTER).apps.get_model("sharing", "SharedList")
    assert not new.objects.filter(pk=row.pk).exists()
    back_to_latest()


@pytest.mark.django_db(transaction=True)
def test_a_live_legacy_list_stops_the_migration_unless_told_to_delete(monkeypatch):
    row = legacy_list("LiveLegacy000000", expires_in=timedelta(days=3))

    with pytest.raises(RuntimeError, match="still alive"):
        migrate(AFTER)

    monkeypatch.setenv("RETIRE_LEGACY_LISTS", "delete")
    executor = migrate(AFTER)
    new = executor.loader.project_state(AFTER).apps.get_model("sharing", "SharedList")
    assert not new.objects.filter(pk=row.pk).exists()
    back_to_latest()
