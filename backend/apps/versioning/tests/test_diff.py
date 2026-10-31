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


def test_compare_lists_every_change_with_before_and_after():
    before = snap("a", "b", "c")
    after = snapshot.build(
        title="New",
        description="",
        links=[
            {"id": "c", "url": "https://example.com/c", "title": "C"},
            {"id": "a", "url": "https://example.com/a2", "title": "A"},
            {"id": "d", "url": "https://example.com/d", "title": "D"},
        ],
    )
    result = diff.compare(before, after)
    assert result["list"] == {"title": {"before": "Tools", "after": "New"}}
    by_id = {change["id"]: change for change in result["links"]}
    assert by_id["d"]["changes"] == ["added"] and by_id["d"]["position_after"] == 2
    assert by_id["b"]["changes"] == ["removed"] and by_id["b"]["position_after"] is None
    assert by_id["a"]["changes"][0] == "modified"
    # [a, c] kept as [c, a]: exactly one of them had to move (which one is a tie).
    assert sum("moved" in by_id.get(i, {"changes": []})["changes"] for i in "ac") == 1
    assert by_id["a"]["fields"] == {
        "url": {"before": "https://example.com/a", "after": "https://example.com/a2"}
    }
    assert [c["id"] for c in result["links"]][-2:] == ["d", "b"]  # new order, removed last
