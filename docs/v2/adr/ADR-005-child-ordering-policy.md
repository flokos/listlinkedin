# ADR-005: Integer positions, move operations, child order preserved

- Status: Accepted (2026-10-28, V2 planning). Positions and move operations are built in
  phase 2. The child-order rules for synchronization are postponed with it
  ([ADR-015](ADR-015-postpone-synchronization.md)).
- Related: [05-DATABASE-DESIGN.md](../05-DATABASE-DESIGN.md), [08 Ordering](../08-SYNCHRONIZATION-SPEC.md#ordering)

## Context

Links need a user-defined order with drag-and-drop that stays consistent under concurrent
edits. V1 has no order column (it sorts newest first). Synced copies may have their own
arrangement. The prompt prefers the simplest reliable approach for the expected scale and the
policy "preserve the child's local order by default".

## Decision

- `SharedLink.position` holds integers `0..n-1` among live links. Deleted links have `NULL`.
  A **deferrable** unique (list, position) constraint is checked at commit. The same applies to
  `GroupList.position`.
- Reordering is a **move** operation (`{link, to_index}`) applied to the current order under
  the list row lock, which renumbers the affected rows. There are no client-supplied full
  orders, so concurrent moves never clobber each other and need no preconditions.
- V1 lists get positions from their current newest-first order.
- Sync: the **child's order is never changed**. Accepted parent additions and revivals are
  appended in the parent's relative order. Parent-only reorders are **not synchronized**, and
  the preview says so.

## Alternatives considered

- **Fractional indexing** (Figma's approach [R18]): inserts without renumbering. It's valuable
  for real-time collaborative editing at scale, but needs rebalancing and longer keys. Lists
  hold ≤100 links and writes are serialized per list, so renumbering a few rows is trivial.
- **Linked list (`after_id`):** cheap inserts, but expensive reads and fragile under
  concurrency.
- **Synchronizing order (sequence merge):** complex, and surprising for users who arranged
  their own copy.

## Consequences

- Simple queries (`ORDER BY position`) and simple invariants (contiguous positions, tested).
- A move rewrites at most n rows (≤100), in milliseconds.
- If live collaborative editing at much larger scale ever appears, revisit with fractional
  keys behind the same move API.
