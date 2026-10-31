# ADR-003: Immutable full revision snapshots in PostgreSQL JSONB

- Status: Accepted (2026-10-28, V2 planning)
- Related: [07-REVISION-SPEC.md](../07-REVISION-SPEC.md), [05-DATABASE-DESIGN.md](../05-DATABASE-DESIGN.md)

## Context

V2 needs list history, restore, consistent branch creation and the BASE, PARENT and CHILD
inputs of a three-way merge. The prompt prefers immutable full snapshots in PostgreSQL and
forbids event sourcing without a compelling reason. Lists are capped at 100 links.

## Decision

- `versioning.ListRevision` stores a **full snapshot** of list *content* (title, description,
  the ordered live links with their user fields) as JSONB, with `schema_version`, a per-list
  `number`, `kind`, `summary`, `restored_from` and the author.
- A revision is written **in the same transaction** as the content change, under the list row
  lock. No-ops write nothing. Settings and fetched metadata are not versioned.
- Revisions are immutable. A database trigger rejects `UPDATE`. A restore writes a new
  revision.
- Live tables stay the source of truth for current state. Invariant R4 keeps the head snapshot
  equal to it.
- Existing V1 lists get one `migrated` baseline revision. No history is fabricated.

## Alternatives considered

- **Change records (deltas):** smaller, but reads replay chains and one bad delta corrupts
  every later state.
- **Event sourcing:** replaces the relational model as the source of truth and needs
  projections and upcasting tooling. That's a rewrite, and no requirement needs it.
- **Hybrid snapshots plus deltas:** an optimization for large documents, which these aren't.

## Consequences

- Any version can be read or restored with one row read. Branch creation and merges read
  immutable data without locking the parent.
- Storage: ~30 KB per revision at the cap, TOAST-compressed. A retention policy can be added
  later without a schema change.
- Every content mutation path must call `record_revision`. Integration and property tests
  (R1, R4) enforce this.
