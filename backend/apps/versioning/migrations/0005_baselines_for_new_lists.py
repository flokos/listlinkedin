# Written by hand (task 3.2). Lists created after 0003 and before mutations recorded revisions
# (between tasks 3.1 and 3.2) have no revision yet: give them the same `migrated` baseline.
# Lists that already have a head are untouched, so this is a no-op on a fresh database.

import importlib

from django.db import migrations

baselines = importlib.import_module("apps.versioning.migrations.0003_baseline_revisions")


class Migration(migrations.Migration):

    dependencies = [
        ("versioning", "0004_strict_immutability"),
    ]

    operations = [migrations.RunPython(baselines.add_baselines, migrations.RunPython.noop)]
