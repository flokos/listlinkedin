"""List content snapshots (docs/v2/07-REVISION-SPEC.md#snapshot-schema-v1).

A snapshot is the content of a list at one revision: its title and description, and its live
links in order with their user-entered fields. Settings (visibility, members, expiry, image…),
fetched metadata, timestamps and short codes are not content and are never in it.

Snapshots are plain dicts, stored as JSONB. Writers always emit CURRENT_VERSION. Readers call
`upcast()`, which brings an older snapshot up to date with the functions in UPCASTERS; stored
rows are never rewritten.
"""

from collections.abc import Callable, Iterable, Mapping
from typing import Any

CURRENT_VERSION = 1

Snapshot = dict[str, Any]

LIST_FIELDS = ("title", "description")
LINK_FIELDS = ("id", "source_link_id", "url", "title", "description", "icon", "position")

# version N → a function turning a version-N snapshot into version N+1. Empty while v1 is the
# only version. Adding v2 means: bump CURRENT_VERSION, write upcast_v1_to_v2, register it here.
UPCASTERS: dict[int, Callable[[Snapshot], Snapshot]] = {}


class InvalidSnapshot(ValueError):
    """A snapshot breaks the schema. Always a bug: snapshots are built, never typed in."""


def build(*, title: str, description: str, links: Iterable[Mapping[str, Any]]) -> Snapshot:
    """The current-version snapshot of a list's content.

    `links` are the live links with the keys of LINK_FIELDS except `position`, in their
    stored order; positions are numbered here. Ids are stringified, and empty optional text is
    `None` (the list's description stays `""`, like its column).
    """
    built = [
        {
            "id": str(link["id"]),
            "source_link_id": _str_or_none(link.get("source_link_id")),
            "url": link["url"],
            "title": link.get("title") or None,
            "description": link.get("description") or None,
            "icon": link.get("icon") or None,
            "position": position,
        }
        for position, link in enumerate(links)
    ]
    snapshot = {
        "schema_version": CURRENT_VERSION,
        "list": {"title": title, "description": description or ""},
        "links": built,
    }
    validate(snapshot)
    return snapshot


def validate(snapshot: Mapping[str, Any]) -> None:
    """Raise InvalidSnapshot unless `snapshot` is a well-formed current-version snapshot."""
    if snapshot.get("schema_version") != CURRENT_VERSION:
        raise InvalidSnapshot(f"Expected schema version {CURRENT_VERSION}.")
    if set(snapshot) != {"schema_version", "list", "links"}:
        raise InvalidSnapshot("Unexpected top-level keys.")
    head = snapshot["list"]
    if not isinstance(head, Mapping) or set(head) != set(LIST_FIELDS):
        raise InvalidSnapshot("`list` must hold exactly title and description.")
    if not isinstance(head["title"], str) or not isinstance(head["description"], str):
        raise InvalidSnapshot("The list's title and description must be strings.")
    links = snapshot["links"]
    if not isinstance(links, list):
        raise InvalidSnapshot("`links` must be a list.")
    ids, urls = set(), set()
    for expected_position, link in enumerate(links):
        if not isinstance(link, Mapping) or set(link) != set(LINK_FIELDS):
            raise InvalidSnapshot(f"Link {expected_position} has the wrong keys.")
        if link["position"] != expected_position:
            raise InvalidSnapshot("Links must be in order with positions 0..n-1.")
        if not isinstance(link["id"], str) or not isinstance(link["url"], str) or not link["url"]:
            raise InvalidSnapshot(f"Link {expected_position} needs a string id and URL.")
        for name in ("source_link_id", "title", "description", "icon"):
            if link[name] is not None and (not isinstance(link[name], str) or not link[name]):
                raise InvalidSnapshot(f"Link {expected_position}: {name} is a string or null.")
        if link["id"] in ids:
            raise InvalidSnapshot(f"Duplicate link id {link['id']}.")
        if link["url"] in urls:
            raise InvalidSnapshot(f"Duplicate URL {link['url']}.")
        ids.add(link["id"])
        urls.add(link["url"])


def upcast(snapshot: Mapping[str, Any]) -> Snapshot:
    """Bring a stored snapshot of any known version up to CURRENT_VERSION."""
    version = snapshot.get("schema_version")
    if not isinstance(version, int) or not 1 <= version <= CURRENT_VERSION:
        raise InvalidSnapshot(f"Unknown schema version {version!r}.")
    current = dict(snapshot)
    while current["schema_version"] < CURRENT_VERSION:
        upgrade = UPCASTERS.get(current["schema_version"])
        if upgrade is None:
            raise InvalidSnapshot(f"No upcaster from version {current['schema_version']}.")
        current = upgrade(current)
    validate(current)
    return current


def same_content(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    """Equal as parsed values, after upcasting: key order and formatting never matter."""
    return upcast(a) == upcast(b)


def _str_or_none(value: Any) -> str | None:
    return None if value is None else str(value)
