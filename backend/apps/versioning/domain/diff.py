"""What changed between two snapshots, as counts for the history list
(docs/v2/07-REVISION-SPEC.md#mutation-rules).

Links are matched by id. A link counts as *moved* only if it has to move: the links kept in
the same relative order (a longest increasing subsequence) don't count, so deleting the first
link isn't reported as moving all the others.
"""

from bisect import bisect_left
from collections.abc import Mapping
from typing import Any

COMPARED_FIELDS = ("source_link_id", "url", "title", "description", "icon")


def summarize(before: Mapping[str, Any] | None, after: Mapping[str, Any]) -> dict[str, Any]:
    """Counts of added, removed, modified and moved links, and the list fields that changed.
    `before` is None for a list's first revision."""
    old = {link["id"]: link for link in (before["links"] if before else [])}
    new = {link["id"]: link for link in after["links"]}
    kept = [link_id for link_id in new if link_id in old]  # in the new order
    modified = sum(
        1 for i in kept if any(old[i][field] != new[i][field] for field in COMPARED_FIELDS)
    )
    old_rank = {link_id: rank for rank, link_id in enumerate(i for i in old if i in new)}
    in_place = _longest_increasing([old_rank[i] for i in kept])
    list_fields = [
        name
        for name in ("title", "description")
        if before is not None and before["list"][name] != after["list"][name]
    ]
    return {
        "added": sum(1 for i in new if i not in old),
        "removed": sum(1 for i in old if i not in new),
        "modified": modified,
        "moved": len(kept) - in_place,
        "list": list_fields,
    }


def _longest_increasing(values: list[int]) -> int:
    tails: list[int] = []
    for value in values:
        at = bisect_left(tails, value)
        if at == len(tails):
            tails.append(value)
        else:
            tails[at] = value
    return len(tails)
