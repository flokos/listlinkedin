"""Revision summaries (apps.versioning.domain.diff): what a history entry reports."""

from apps.versioning.domain import diff, snapshot


def snap(*names, title="Tools", **changed):
    links = [
        {"id": n, "url": f"https://example.com/{n}", "title": changed.get(n, n.upper())}
        for n in names
    ]
    return snapshot.build(title=title, description="", links=links)


def counts(before, after):
    return diff.summarize(before, after)


def test_first_revision_counts_every_link_as_added():
    assert counts(None, snap("a", "b")) == {
        "added": 2,
        "removed": 0,
        "modified": 0,
        "moved": 0,
        "list": [],
    }


def test_adds_removes_and_edits():
    result = counts(snap("a", "b", "c"), snap("a", "c", "d", c="Renamed"))
    assert (result["added"], result["removed"], result["modified"]) == (1, 1, 1)
    assert result["moved"] == 0  # deleting b shifts c, but c didn't move relative to a


def test_moves_count_only_links_that_had_to_move():
    assert counts(snap("a", "b", "c", "d"), snap("b", "c", "d", "a"))["moved"] == 1
    assert counts(snap("a", "b", "c", "d"), snap("d", "c", "b", "a"))["moved"] == 3
    assert counts(snap("a", "b"), snap("a", "b"))["moved"] == 0


def test_list_field_changes_are_named():
    before = snap("a")
    after = snapshot.build(title="New name", description="Notes", links=before["links"])
    assert counts(before, after)["list"] == ["title", "description"]
