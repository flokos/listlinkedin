# ADR-002: Modular monolith with a small pure domain core

- Status: Accepted (2026-10-28, V2 planning)
- Related: [03-ARCHITECTURE.md](../03-ARCHITECTURE.md)

## Context

The prompt asks for Onion/Hexagonal direction (domain independent of Django), SOLID, and also
KISS, YAGNI and "pragmatism over purity". V1 is a two-app Django monolith in which views call
services that use the ORM directly. It deliberately has no repository layer, and its services
raise DRF exceptions. V2 adds one genuinely complex domain problem (three-way merge) and one
cross-cutting rule set (authorization), plus a lot of ordinary CRUD.

## Decision

- Stay a single Django project, a single PostgreSQL database and a single deployable, with one
  extra process type (the worker) built from the same image.
- Bounded contexts are Django apps: `sharing`, `shortener`, `accounts`, `groups`,
  `versioning`, `metadata`. Apps call each other's services and selectors, never each other's
  model writes.
- A **framework-free domain core** exists only where correctness risk justifies it:
  `versioning/domain` (snapshot schema, diff and merge, domain errors) and `sharing/policy.py`
  (permission rules). It is enforced by an import test.
- Everything else follows the V1 pattern: ViewSets → services (transactions and locks) →
  ORM, with selectors for reads. No generic repositories, unit-of-work objects or DTO layers.
  Use-case-specific loaders feed the pure core plain data.
- New code raises domain errors, which one exception handler maps to HTTP. V1 code that raises
  DRF exceptions changes only when touched.

## Alternatives considered

- **Full hexagonal layering for every use case.** Repositories mirroring the ORM, ports and
  adapters for CRUD. A lot of code that duplicates Django and protects little. Rejected (prompt
  7.4).
- **Microservices** (shortener, sync, metadata). Distributed transactions across lists,
  revisions and short codes, and more infrastructure. Rejected (prompt 1.3).
- **No pure core at all.** The merge engine would become hard to test exhaustively, because
  every test would need a database. Rejected for the high-risk parts.

## Consequences

- The merge engine and policy get fast, exhaustive unit and property tests.
- One small mutual dependency (`sharing` ↔ `versioning`) exists at the service level and is
  documented. Revisions must be written inside list mutations.
- Contributors need to know which modules are "pure". CLAUDE.md and the import test make that
  explicit.
