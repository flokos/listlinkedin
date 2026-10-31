# ADR-013: Soft-delete Links only; hard-delete Lists and Groups

- Status: Accepted (2026-10-28, V2 planning)
- Related: [04 Deviations](../04-DOMAIN-MODEL.md#deviations-from-the-proposed-baseline), [05 Deletion semantics](../05-DATABASE-DESIGN.md#deletion-semantics)

## Context

The prompt's baseline gives Lists, Links and Groups a `deleted_at` column and asks that
deletion never destroy required history. Links need stable identity across deletion and
restore: revisions reference link ids, a restore should bring back the same link and short
URL, and sync matches child copies by source id. Lists and groups have no such need. Their
children (branches) keep their own copies and history.

## Decision

- **Links are soft-deleted** (tombstones: `deleted_at` set, `position` NULL, redirect row
  kept, short URL 404). Restore and sync revive the same row. Tombstones live as long as the
  list.
- **Lists and Groups are hard-deleted**, as in V1, after a type-to-confirm dialog. Before a
  list is deleted, its branches get `parent_deleted_at`, and their parent and base references
  become NULL. Children keep everything they have.
- Expired lists are purged as in V1.

## Alternatives considered

- **Soft-delete everything:** every query, count, search, group view and short-URL resolution
  must filter deleted lists. One missed filter is a data leak (risk 8). It also implies a
  trash and undo UX nobody requested.
- **Hard-delete links:** breaks revision restore (ids would be reused or missing), short-URL
  revival and sync identity.

## Consequences

- Fewer leak paths and simpler queries for lists and groups.
- No undo for list deletion in the MVP (open question Q7, with a safe design noted: an archive
  table instead of soft-delete filters).
- Link tables keep tombstones. Their cost is bounded by usage and is negligible.
