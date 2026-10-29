"""What changed between two snapshots (docs/v2/07-REVISION-SPEC.md#mutation-rules).

Links are matched by id. A link counts as *moved* only if it has to move: the links kept in
the same relative order (a longest increasing subsequence) don't count, so deleting the first
link isn't reported as moving all the others.

`summarize` gives the counts stored with each revision; `compare` gives the full list of
changes shown when a revision is opened.
"""

from bisect import bisect_left
from collections.abc import Mapping
from typing import Any

COMPARED_FIELDS = ("source_link_id", "url", "title", "description", "icon")
LIST_FIELDS = ("title", "description")


def summarize(before: Mapping[str, Any] | None, after: Mapping[str, Any]) -> dict[str, Any]:
    """Counts of added, removed, modified and moved links, and the list fields that changed.
    `before` is None for a list's first revision."""
    changes = compare(before, after)
    counts = {"added": 0, "removed": 0, "modified": 0, "moved": 0}
    for change in changes["links"]:
        for kind in change["changes"]:
            counts[kind] += 1
    return {**counts, "list": list(changes["list"])}


def compare(before: Mapping[str, Any] | None, after: Mapping[str, Any]) -> dict[str, Any]:
    """Every difference from `before` to `after`.

    `list` maps each changed list field to `{"before", "after"}`. `links` has one entry per
    link that changed, in the order of `after` (removed links last, in their old order), each
    with its id, url and title (as of `after`, or `before` if removed), `changes` (a subset of
    added, removed, modified, moved), the positions, and the changed fields with both values.
    """
    old = {link["id"]: link for link in (before["links"] if before else [])}
    new = {link["id"]: link for link in after["links"]}
    kept = [link_id for link_id in new if link_id in old]
    old_rank = {link_id: rank for rank, link_id in enumerate(i for i in old if i in new)}
    in_place = _in_order(kept, old_rank)

    links = []
    for link_id, link in new.items():
        previous = old.get(link_id)
        entry = _entry(link, previous, link)
        if previous is None:
            entry["changes"].append("added")
        else:
            fields = {
                name: {"before": previous[name], "after": link[name]}
                for name in COMPARED_FIELDS
                if previous[name] != link[name]
            }
            if fields:
                entry["changes"].append("modified")
                entry["fields"] = fields
            if link_id not in in_place:
                entry["changes"].append("moved")
        if entry["changes"]:
            links.append(entry)
    for link_id, previous in old.items():
        if link_id not in new:
            entry = _entry(previous, previous, None)
            entry["changes"].append("removed")
            links.append(entry)

    list_changes = {}
    if before is not None:
        for name in LIST_FIELDS:
            if before["list"][name] != after["list"][name]:
                list_changes[name] = {"before": before["list"][name], "after": after["list"][name]}
    return {"list": list_changes, "links": links}


def _entry(shown, previous, current) -> dict[str, Any]:
    return {
        "id": shown["id"],
        "url": shown["url"],
        "title": shown["title"],
        "changes": [],
        "position_before": previous["position"] if previous else None,
        "position_after": current["position"] if current else None,
        "fields": {},
    }


def _in_order(kept: list[str], old_rank: dict[str, int]) -> set[str]:
    """The kept links that stay in relative order: a longest increasing subsequence of their
    old ranks, taken in their new order."""
    ranks = [old_rank[link_id] for link_id in kept]
    tails: list[int] = []  # index into ranks of the smallest tail of each length
    parent: list[int | None] = [None] * len(ranks)
    for i, rank in enumerate(ranks):
        at = bisect_left([ranks[t] for t in tails], rank)
        parent[i] = tails[at - 1] if at else None
        if at == len(tails):
            tails.append(i)
        else:
            tails[at] = i
    result: set[str] = set()
    i = tails[-1] if tails else None
    while i is not None:
        result.add(kept[i])
        i = parent[i]
    return result
