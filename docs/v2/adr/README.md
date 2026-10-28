# Architecture Decision Records

Short records of the decisions that shape V2. Each has a context, the decision, the
alternatives considered, the consequences and a status. The format follows the common
Nygard/MADR layout.

## Rules

- ADRs are **binding** for V2 work ([CLAUDE.md](../../../CLAUDE.md)).
- Don't edit an accepted ADR's decision. Write a new ADR that supersedes it, and set the old
  one's status to "Superseded by ADR-NNN". Typo and link fixes are fine.
- A PR that changes architecture adds or supersedes an ADR **in the same PR** and updates the
  affected `docs/v2/` documents.
- Number sequentially. Filename: `ADR-NNN-short-title.md`.

## Index

| ADR | Title | Status |
|---|---|---|
| [001](ADR-001-preserve-list-and-link.md) | Preserve List and Link (`SharedList`/`SharedLink`) | Accepted |
| [002](ADR-002-modular-monolith.md) | Modular monolith with a small pure domain core | Accepted |
| [003](ADR-003-immutable-revision-snapshots.md) | Immutable full revision snapshots in PostgreSQL JSONB | Accepted |
| [004](ADR-004-three-way-merge.md) | Three-way merge with a branch-level baseline | Accepted |
| [005](ADR-005-child-ordering-policy.md) | Integer positions, move operations, child order preserved | Accepted |
| [006](ADR-006-url-shortening-strategy.md) | URL shortening: keep V1 codes, no polymorphic ShortURL, no external targets | Accepted |
| [007](ADR-007-authentication-and-ownership-migration.md) | Custom user, session auth with allauth headless, claim-based ownership migration | Accepted |
| [008](ADR-008-background-metadata-extraction.md) | Background metadata extraction on a PostgreSQL-backed worker | Accepted |
| [009](ADR-009-git-v2-integration-branch.md) | Git: `v2` integration branch, CI guard, rulesets | Accepted |
| [010](ADR-010-viewsets-and-api-v2.md) | DRF ViewSets under `/api/v2/`; `/api/v1/` kept for the transition | Accepted |
| [011](ADR-011-accounts-required-legacy-lists.md) | Accounts required to create lists; V1 lists become legacy lists | Accepted |
| [012](ADR-012-media-and-images.md) | Media: Pillow re-encoding, same-origin serving | Accepted |
| [013](ADR-013-soft-delete-links-only.md) | Soft-delete Links only; hard-delete Lists and Groups | Accepted |
| [014](ADR-014-django-version.md) | Stay on Django 5.2 LTS for V2; move to 6.2 LTS afterwards | Accepted |
