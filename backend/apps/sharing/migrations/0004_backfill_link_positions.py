# Written by hand (task 2.1). Gives every existing link a position that keeps today's
# on-screen order, newest first, as the initial manual order (docs/v2/06-MIGRATION-PLAN.md).
# Runs per batch of lists, so no single statement holds locks on the whole table.

from django.db import migrations

BATCH = 500

NUMBER_LINKS = """
    UPDATE sharing_sharedlink AS link
    SET position = ranked.n
    FROM (
        SELECT id, ROW_NUMBER() OVER (
            PARTITION BY shared_list_id ORDER BY created_at DESC, id DESC
        ) - 1 AS n
        FROM sharing_sharedlink
        WHERE shared_list_id = ANY(%s)
    ) AS ranked
    WHERE link.id = ranked.id
"""


def backfill_positions(apps, schema_editor):
    SharedList = apps.get_model("sharing", "SharedList")
    ids = SharedList.objects.order_by("pk").values_list("pk", flat=True)
    batch = []
    with schema_editor.connection.cursor() as cursor:
        for list_id in ids.iterator(chunk_size=BATCH):
            batch.append(list_id)
            if len(batch) == BATCH:
                cursor.execute(NUMBER_LINKS, [batch])
                batch = []
        if batch:
            cursor.execute(NUMBER_LINKS, [batch])


class Migration(migrations.Migration):

    dependencies = [
        ('sharing', '0003_link_fields'),
    ]

    operations = [
        # Reverse: positions are simply dropped again by reversing 0003.
        migrations.RunPython(backfill_positions, migrations.RunPython.noop),
    ]
