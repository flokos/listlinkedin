# Written by hand (task 3.1). Every list that exists before V2 gets revision 1, kind
# `migrated`: a snapshot of its content at migration time. No earlier history is invented
# (docs/v2/06-MIGRATION-PLAN.md#revision-initialization).
#
# The snapshot is built in SQL, per batch of lists, in the frozen v1 format of
# docs/v2/07-REVISION-SPEC.md (a test checks it equals apps.versioning.domain.snapshot.build).
# Lists that already have a revision (head_revision > 0) are skipped, so re-running is safe.

from django.db import migrations

BATCH = 500

INSERT_BASELINES = """
    INSERT INTO versioning_listrevision
        (id, shared_list_id, number, schema_version, kind, snapshot, summary, created_at)
    SELECT
        gen_random_uuid(), l.id, 1, 1, 'migrated',
        jsonb_build_object(
            'schema_version', 1,
            'list', jsonb_build_object('title', l.title, 'description', l.description),
            'links', COALESCE((
                SELECT jsonb_agg(jsonb_build_object(
                    'id', k.id::text,
                    'source_link_id', k.source_link_id::text,
                    'url', k.destination_url,
                    'title', NULLIF(k.title, ''),
                    'description', NULLIF(k.description, ''),
                    'icon', NULLIF(k.icon, ''),
                    'position', k.position
                ) ORDER BY k.position)
                FROM sharing_sharedlink AS k
                WHERE k.shared_list_id = l.id AND k.deleted_at IS NULL
            ), '[]'::jsonb)
        ),
        '{}'::jsonb,
        now()
    FROM sharing_sharedlist AS l
    WHERE l.id = ANY(%s) AND l.head_revision = 0
"""

SET_HEADS = "UPDATE sharing_sharedlist SET head_revision = 1 WHERE id = ANY(%s) AND head_revision = 0"


def add_baselines(apps, schema_editor):
    SharedList = apps.get_model("sharing", "SharedList")
    ids = SharedList.objects.filter(head_revision=0).order_by("pk").values_list("pk", flat=True)
    batch = []
    with schema_editor.connection.cursor() as cursor:
        for list_id in ids.iterator(chunk_size=BATCH):
            batch.append(list_id)
            if len(batch) == BATCH:
                cursor.execute(INSERT_BASELINES, [batch])
                cursor.execute(SET_HEADS, [batch])
                batch = []
        if batch:
            cursor.execute(INSERT_BASELINES, [batch])
            cursor.execute(SET_HEADS, [batch])


def remove_baselines(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "UPDATE sharing_sharedlist SET head_revision = 0 WHERE id IN ("
            " SELECT shared_list_id FROM versioning_listrevision"
            " WHERE kind = 'migrated' AND number = 1)"
            " AND head_revision = 1"
        )
        cursor.execute("DELETE FROM versioning_listrevision WHERE kind = 'migrated'")


class Migration(migrations.Migration):

    dependencies = [
        ("versioning", "0002_revision_immutable_trigger"),
    ]

    operations = [migrations.RunPython(add_baselines, remove_baselines)]
