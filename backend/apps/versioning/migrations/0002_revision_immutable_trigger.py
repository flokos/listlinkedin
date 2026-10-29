# Written by hand (task 3.1). Revisions are immutable (docs/v2/07-REVISION-SPEC.md#immutability):
# the database rejects any UPDATE, whoever sends it. DELETE stays possible, so deleting a list
# removes its history.
#
# One update is allowed: clearing `created_by_id` and nothing else. That is what deleting an
# account does to the revisions it wrote on other people's lists (on_delete=SET_NULL), and the
# revision's content is untouched by it.

from django.db import migrations

CREATE = """
CREATE FUNCTION versioning_revision_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.created_by_id IS NULL
       AND to_jsonb(NEW) - 'created_by_id' = to_jsonb(OLD) - 'created_by_id' THEN
        RETURN NEW;  -- the author's account was deleted
    END IF;
    RAISE EXCEPTION 'list revisions are immutable (revision %)', OLD.id
        USING ERRCODE = 'restrict_violation';
END
$$;

CREATE TRIGGER versioning_revision_immutable
    BEFORE UPDATE ON versioning_listrevision
    FOR EACH ROW EXECUTE FUNCTION versioning_revision_immutable();
"""

DROP = """
DROP TRIGGER versioning_revision_immutable ON versioning_listrevision;
DROP FUNCTION versioning_revision_immutable();
"""


class Migration(migrations.Migration):

    dependencies = [
        ("versioning", "0001_initial"),
    ]

    operations = [migrations.RunSQL(CREATE, DROP)]
