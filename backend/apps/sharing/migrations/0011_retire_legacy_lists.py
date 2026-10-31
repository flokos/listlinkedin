# The legacy sunset (task 9.6, docs/v2/06-MIGRATION-PLAN.md#after-launch-contracting-the-legacy-path):
# every list belongs to an account from now on. Edit-link lists (no owner) that have expired
# are deleted, as `cleanup_expired` would; a live one stops the migration, because it would
# lose its only manager. V1 was never deployed (D32), so only development databases can have
# one: RETIRE_LEGACY_LISTS=delete deletes those too.
#
# The schema change follows in 0012, in its own transaction: PostgreSQL can't alter a table
# while checks deferred by these deletes are pending. Deleted lists don't come back on reverse.

import os

from django.conf import settings
from django.db import migrations
from django.utils import timezone


def delete_expired_legacy_lists(apps, schema_editor):
    SharedList = apps.get_model("sharing", "SharedList")
    legacy = SharedList.objects.filter(owner__isnull=True)
    if os.environ.get("RETIRE_LEGACY_LISTS") != "delete":
        legacy = legacy.filter(expires_at__lte=timezone.now())
    legacy.delete()
    alive = SharedList.objects.filter(owner__isnull=True).count()
    if alive:
        raise RuntimeError(
            f"{alive} list(s) without an account are still alive (edit-link lists). Run a "
            "v2.0.x release until they expire (at most 30 days), then migrate again. Or, to "
            "delete them now with their links and short URLs, migrate with "
            "RETIRE_LEGACY_LISTS=delete."
        )


class Migration(migrations.Migration):
    # The apps whose rows a deleted list cascades to, so their models are in this state.
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("sharing", "0010_directory_title_index"),
        ("groups", "0003_directory_title_index"),
        ("shortener", "0001_initial"),
        ("versioning", "0005_baselines_for_new_lists"),
    ]

    operations = [
        migrations.RunPython(delete_expired_legacy_lists, migrations.RunPython.noop),
    ]
