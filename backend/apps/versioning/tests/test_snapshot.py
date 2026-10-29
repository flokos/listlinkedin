"""Snapshot schema v1 (docs/v2/07-REVISION-SPEC.md#snapshot-schema-v1): pure, no database."""

import copy
import uuid

import pytest

from apps.versioning.domain import snapshot
from apps.versioning.domain.snapshot import InvalidSnapshot


def link(n: int, **fields):
    return {"id": f"id-{n}", "url": f"https://example.com/{n}", **fields}


def make(*links, title="Tools", description=""):
    return snapshot.build(title=title, description=description, links=links)


def test_build_numbers_positions_and_normalizes_empty_fields():
    built = make(link(1, title="", description=None, icon=""), link(2, title="Two"))
    assert built == {
        "schema_version": 1,
        "list": {"title": "Tools", "description": ""},
        "links": [
            {
                "id": "id-1",
                "source_link_id": None,
                "url": "https://example.com/1",
                "title": None,
                "description": None,
                "icon": None,
                "position": 0,
            },
            {
                "id": "id-2",
                "source_link_id": None,
                "url": "https://example.com/2",
                "title": "Two",
                "description": None,
                "icon": None,
                "position": 1,
            },
        ],
    }


def test_ids_are_stringified():
    link_id, source = uuid.uuid4(), uuid.uuid4()
    built = make({"id": link_id, "source_link_id": source, "url": "https://example.com/"})
    assert built["links"][0]["id"] == str(link_id)
    assert built["links"][0]["source_link_id"] == str(source)


@pytest.mark.parametrize(
    "break_it",
    [
        lambda s: s.update(schema_version=2),
        lambda s: s.update(extra=1),
        lambda s: s["list"].pop("description"),
        lambda s: s["list"].update(title=None),
        lambda s: s["links"][1].update(position=5),  # positions must be 0..n-1
        lambda s: s["links"].reverse(),  # out of order
        lambda s: s["links"][1].update(id="id-1"),  # duplicate id
        lambda s: s["links"][1].update(url="https://example.com/1"),  # duplicate URL
        lambda s: s["links"][0].update(title=""),  # empty text is null, not ""
        lambda s: s["links"][0].update(icon=7),
        lambda s: s["links"][0].pop("icon"),
        lambda s: s["links"][0].update(url=""),
    ],
)
def test_validate_rejects_broken_snapshots(break_it):
    broken = copy.deepcopy(make(link(1), link(2)))
    break_it(broken)
    with pytest.raises(InvalidSnapshot):
        snapshot.validate(broken)


def test_content_is_compared_as_values_not_text():
    a = make(link(1, title="A"))
    reordered_keys = {
        "links": [dict(reversed(list(a["links"][0].items())))],
        "list": {"description": "", "title": "Tools"},
        "schema_version": 1,
    }
    assert snapshot.same_content(a, reordered_keys)
    assert not snapshot.same_content(a, make(link(1, title="B")))


def test_upcasting_brings_old_snapshots_to_the_current_version(monkeypatch):
    """The hook a v2 schema will use: stored v1 rows are read through an upcaster."""
    stored_v1 = make(link(1, title="A"))

    def upcast_v1_to_v2(old):
        return {**old, "schema_version": 2}

    def validate_v2(s):
        assert s["schema_version"] == 2

    monkeypatch.setattr(snapshot, "CURRENT_VERSION", 2)
    monkeypatch.setitem(snapshot.UPCASTERS, 1, upcast_v1_to_v2)
    monkeypatch.setattr(snapshot, "validate", validate_v2)
    assert snapshot.upcast(stored_v1)["schema_version"] == 2
    assert stored_v1["schema_version"] == 1  # the stored row is never rewritten


def test_unknown_versions_are_refused(monkeypatch):
    stored_v1 = make()
    with pytest.raises(InvalidSnapshot, match="Unknown schema version"):
        snapshot.upcast({**stored_v1, "schema_version": 9})
    monkeypatch.setattr(snapshot, "CURRENT_VERSION", 2)  # v2 exists, but nobody wrote v1→v2
    with pytest.raises(InvalidSnapshot, match="No upcaster"):
        snapshot.upcast(stored_v1)
