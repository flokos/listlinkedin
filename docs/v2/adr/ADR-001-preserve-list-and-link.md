# ADR-001: Preserve List and Link

- Status: Accepted (2026-10-28, V2 planning)
- Related: [04-DOMAIN-MODEL.md](../04-DOMAIN-MODEL.md), [01-V1-AUDIT.md](../01-V1-AUDIT.md)

## Context

V2 adds tiles that represent web applications, groups, revisions and synced copies. It's
tempting to introduce new central entities, such as a global `WebApp` catalogue or a
`BranchedList` subtype. V1 implements the core as `sharing.SharedList` and
`sharing.SharedLink`, with tables `sharing_sharedlist` and `sharing_sharedlink`, UUID keys,
stable public codes and short URLs that depend on these rows. The product owner decided to
keep List and Link as the central concepts.

## Decision

- **List** and **Link** stay the core of the model. Their V1 classes, tables and primary keys
  are kept. The docs use "List" and "Link". The code keeps `SharedList` and `SharedLink`, and
  the glossary maps the two.
- No `WebApp` entity. A tile is a Link with a description and an icon. Fetched metadata lives
  on the Link.
- No `BranchedList` subtype. Forks and branches are ordinary Lists. A branch relationship is a
  separate `ListBranch` row.
- A Link's identity is its `id`, not its URL (invariant K1).

## Alternatives considered

- **Rename to `List`/`Link`.** This is cosmetic. Renaming tables and models touches every
  migration, query and test for no behavioural gain, and the prompt says not to reorganize for
  cosmetic consistency.
- **A global WebApp table referenced by Links.** Deduplicated metadata, but it adds a shared
  mutable entity whose edits would leak across unrelated lists, and it complicates permissions
  and sync. There's no demonstrated need.
- **Subtypes for branches.** Multi-table inheritance would complicate every list query and
  doesn't express anything a relationship row can't.

## Consequences

- V1 data and URLs carry over with no identity changes. The migration is additive.
- Readers must learn one mapping, provided in the glossary.
- The same URL appears as separate Links in different lists, each with its own fetched
  metadata. Deduplicating fetches by URL is possible later, inside the metadata app, without
  changing the model.
