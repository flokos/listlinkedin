"""V1 rows survive the ownership migration as legacy lists (docs/v2/06-MIGRATION-PLAN.md)."""

from datetime import timedelta

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

BEFORE = [("sharing", "0001_initial")]
AFTER = [("sharing", "0002_list_ownership")]


@pytest.mark.django_db(transaction=True)
def test_v1_lists_become_unlisted_legacy_lists_with_identity_kept():
    executor = MigrationExecutor(connection)
    executor.migrate(BEFORE)
    old = executor.loader.project_state(BEFORE).apps.get_model("sharing", "SharedList")
    expires = timezone.now() + timedelta(days=12)
    row = old.objects.create(
        public_code="V1CodeKeptAsIs00",
        owner_token_hash="a" * 64,
        title="Manage",  # a reserved slug
        expires_at=expires,
    )

    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(AFTER)
    new = executor.loader.project_state(AFTER).apps.get_model("sharing", "SharedList")
    migrated = new.objects.get(pk=row.pk)

    assert migrated.public_code == "V1CodeKeptAsIs00"
    assert migrated.owner_token_hash == "a" * 64
    assert migrated.owner_id is None
    assert migrated.visibility == "unlisted"
    assert migrated.expires_at == expires
    assert migrated.slug == "manage-list"

    # Back to the latest state for the tests that follow.
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes())
