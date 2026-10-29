# Written by hand (task 3.0 merged with 3.1). Since docs/v2/adr/ADR-016 user rows are never
# deleted (erased accounts keep an anonymous row), so nothing clears a revision's author any
# more: the trigger goes back to rejecting every UPDATE, with no exception.

from django.db import migrations

STRICT = """
CREATE OR REPLACE FUNCTION versioning_revision_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'list revisions are immutable (revision %)', OLD.id
        USING ERRCODE = 'restrict_violation';
END
$$;
"""

# The previous version, from 0002 (lets an author's account deletion clear created_by_id).
LENIENT = """
CREATE OR REPLACE FUNCTION versioning_revision_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.created_by_id IS NULL
       AND to_jsonb(NEW) - 'created_by_id' = to_jsonb(OLD) - 'created_by_id' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'list revisions are immutable (revision %)', OLD.id
        USING ERRCODE = 'restrict_violation';
END
$$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("versioning", "0003_baseline_revisions"),
    ]

    operations = [migrations.RunSQL(STRICT, LENIENT)]
