# Every list has an owner account (task 9.6): the owner is required, and the token column and
# the checks for ownerless lists (L2, L3) go. 0011 removed the rows this would refuse.
# Reversible in development: the constraints and the (empty) column come back, and the owner
# becomes nullable again.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("sharing", "0011_retire_legacy_lists"),
    ]

    operations = [
        migrations.RemoveConstraint(model_name="sharedlist", name="sharing_list_has_manager"),
        migrations.RemoveConstraint(
            model_name="sharedlist", name="sharing_list_legacy_unlisted_expiring"
        ),
        migrations.RemoveField(model_name="sharedlist", name="owner_token_hash"),
        migrations.AlterField(
            model_name="sharedlist",
            name="owner",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="owned_lists",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
