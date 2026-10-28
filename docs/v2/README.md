# listlinkedin Version 2: architecture and migration plan

Status: **planning complete, implementation not started** (2026-10-28).
Branch: `v2`, created from `main` at `fb5f901` (V1 as of PR #7). Source requirements:
[project_prompt_for_Planning_v2.md](../../project_prompt_for_Planning_v2.md). V1 is described
by the root [README.md](../../README.md) and [docs/](../).

Version 2 turns the anonymous, 30-day link lists of V1 into a collaborative platform. People
have accounts. Lists can be private, unlisted or public, and can be permanent. Groups collect
lists into a workspace with a sidebar. Every list keeps an immutable revision history. Copies
can stay in sync with their source through a three-way merge the user reviews. Links show as
application tiles with fetched metadata. A public directory makes lists discoverable. **A List
contains Links** stays the core of the model.

## How to read this

| If you are… | Read |
|---|---|
| Starting any V2 task | [CLAUDE.md](../../CLAUDE.md), then this page, then the roadmap task's linked specs |
| Working on the backend | 04 → 05 → 12 → 09, then 07/08 for versioning work |
| Working on the frontend | 10 → 11 → 09 |
| Reviewing risk or security | 13 → 18 → 12 |
| Planning work | 17 → 20 |

## Documents

| # | Document | Contents |
|---|---|---|
| 01 | [V1 audit](01-V1-AUDIT.md) | What V1 actually is: code, API, UI, infrastructure, tests, debt, reuse |
| 02 | [Product requirements](02-PRODUCT-REQUIREMENTS.md) | Every V2 feature, classed as MVP, later or deferred |
| 03 | [Architecture](03-ARCHITECTURE.md) | Components, layers, dependency direction, module responsibilities |
| 04 | [Domain model](04-DOMAIN-MODEL.md) | Entities, aggregates, value objects, invariants, domain services |
| 05 | [Database design](05-DATABASE-DESIGN.md) | Schema, ER diagram, constraints, indexes, deletion, transactions |
| 06 | [Migration plan](06-MIGRATION-PLAN.md) | V1 → V2 schema and data migration, ownership transition, rollout, rollback |
| 07 | [Revision spec](07-REVISION-SPEC.md) | Snapshot schema, numbering, mutation rules, restore, concurrency |
| 08 | [Synchronization spec](08-SYNCHRONIZATION-SPEC.md) | Branch/fork, three-way diff, decisions, baselines, every scenario |
| 09 | [API design](09-API-DESIGN.md) | `/api/v2/` endpoints, payloads, errors, preconditions, idempotency |
| 10 | [Frontend architecture](10-FRONTEND-ARCHITECTURE.md) | Current structure, reuse, new modules, state, API integration |
| 11 | [UI/UX migration](11-UI-UX-MIGRATION.md) | Screens, journeys, responsive layout, merge preview UX, states, a11y |
| 12 | [Authorization](12-AUTHORIZATION.md) | Roles, the permission matrix, visibility rules, leak analysis |
| 13 | [Security](13-SECURITY.md) | Threat model and mitigations |
| 14 | [Infrastructure](14-INFRASTRUCTURE.md) | Services and why each exists, minimal vs optional setups |
| 15 | [Test strategy](15-TEST-STRATEGY.md) | Test levels, acceptance matrix, V1 regression checklist |
| 16 | [Git workflow](16-GIT-WORKFLOW.md) | `main`/`v2` coexistence, PR targets, CI guard, rulesets, fixes |
| 17 | [Implementation roadmap](17-IMPLEMENTATION-ROADMAP.md) | Phases 0–9 as PR-sized tasks, dependencies, parallelism |
| 18 | [Risks and mitigations](18-RISKS-AND-MITIGATIONS.md) | Prioritized risk register |
| 19 | [Research references](19-RESEARCH-REFERENCES.md) | Sources, dates, what was verified and how |
| 20 | [Decisions and open questions](20-DECISIONS-AND-OPEN-QUESTIONS.md) | Decision log, open questions |
| — | [ADRs](adr/README.md) | Architecture Decision Records ADR-001 … ADR-014 |

Diagrams are Mermaid blocks inside the documents (GitHub renders them), so there is no separate
diagrams folder.

## Labels used in these documents

| Label | Meaning |
|---|---|
| **[Observed]** | Seen in the V1 repository at `fb5f901` |
| **[Verified Rn]** | Checked against source *Rn* in [19-RESEARCH-REFERENCES.md](19-RESEARCH-REFERENCES.md) during this planning run |
| **[Assumption]** | Believed true but not verified. Each one names how to verify it |
| **[Decision]** | Settled for V2. Changing it needs a new ADR |
| **[Open]** | Not settled. Listed in [20](20-DECISIONS-AND-OPEN-QUESTIONS.md) with a recommendation |

## Glossary

| Term | Meaning | In code |
|---|---|---|
| List | A collection of Links with a stable identity | `sharing.SharedList` (table `sharing_sharedlist`) |
| Link | One URL entry in a List. Its identity is its `id`, not its URL | `sharing.SharedLink` |
| Code | 16-character random Base64URL identifier: a List's `public_code`, a Group's `code`, a Link's short code | `shortener.generators` |
| Short URL | `/l/{code}` (list), `/g/{code}` (group), `/r/{code}` (link redirect) | `config/urls.py`, nginx |
| Owner | The account that owns a List or Group (`owner_id`) | |
| Member | A user with an EDITOR or VIEWER role on one List or Group | `ListMembership`, `GroupMembership` |
| Legacy list | A V1 list with no owner account, managed through its owner token (edit link) | `owner_id IS NULL` |
| Claim | Turning a legacy list into an account-owned list by proving the token | |
| Revision | Immutable, numbered full snapshot of a List's content | `versioning.ListRevision` |
| Fork | An independent copy with no sync relationship ("Make a copy") | |
| Branch | A copy that can pull changes from its parent ("Make a synced copy") | `versioning.ListBranch` |
| Parent / child | Source list / synced copy of a branch | |
| Source link | The parent Link a child Link was copied from (`source_link_id`) | |
| Base / baseline | The parent revision the child last synchronized against | `ListBranch.base_revision` |
| Exclusion | A persistent "ignore this source link" rule on a branch | `versioning.BranchExclusion` |
| Group | An ordered workspace of Lists that never duplicates their content | `groups.Group` |
| Visibility | PRIVATE (members only), UNLISTED (anyone with the URL), PUBLIC (also in the directory) | |

In the UI, product language replaces the Git terms. A branch is a "synced copy", the parent is
the "source list", a merge is "Get updates", and an exclusion is "Ignore this link". See
[11-UI-UX-MIGRATION.md](11-UI-UX-MIGRATION.md).

## Decision summary

These are the decisions everything else builds on. The details are in the linked ADRs and specs.

1. **Keep `SharedList`/`SharedLink`** and their tables. No `WebApp` entity. ([ADR-001](adr/ADR-001-preserve-list-and-link.md))
2. **Modular monolith** with pragmatic layering. Framework-free code is used only where the
   risk is: snapshots, diff/merge and the permission policy. ([ADR-002](adr/ADR-002-modular-monolith.md))
3. **Accounts are required to create lists.** V1 lists stay manageable through their edit link
   until they are claimed or expire. ([ADR-011](adr/ADR-011-accounts-required-legacy-lists.md))
4. **A custom `User` in a new `accounts` app**, plus Django session auth with CSRF and
   django-allauth in headless browser mode. V1 has no auth tables, so this is a clean
   introduction. ([ADR-007](adr/ADR-007-authentication-and-ownership-migration.md))
5. **`/api/v2/` with DRF ViewSets.** `/api/v1/` stays for legacy lists during the transition.
   ([ADR-010](adr/ADR-010-viewsets-and-api-v2.md))
6. **Visibility** is PRIVATE, UNLISTED or PUBLIC. New lists default to PRIVATE. Migrated V1
   lists become UNLISTED, which is what they are today.
7. **Slugs are cosmetic** (`/l/{code}/{slug}`). They are never identifiers, so they never
   collide or break.
8. **Short URLs keep V1's 96-bit codes.** Groups get `/g/{code}`. Every resolution re-checks
   visibility. EXTERNAL_URL targets are deferred. ([ADR-006](adr/ADR-006-url-shortening-strategy.md))
9. **Links are soft-deleted** (tombstones that keep identity and short code). Lists and Groups
   are hard-deleted. ([ADR-013](adr/ADR-013-soft-delete-links-only.md))
10. **Ordering uses integer positions and "move" operations** under the list row lock.
    Children keep their own order. ([ADR-005](adr/ADR-005-child-ordering-policy.md))
11. **Revisions are immutable full JSONB snapshots**, numbered per list and written in the
    mutation's transaction. ([ADR-003](adr/ADR-003-immutable-revision-snapshots.md))
12. **Three-way merge** with a branch-level baseline, ACCEPT / KEEP_LOCAL / EXCLUDE decisions,
    a preview fingerprint and idempotent apply. ([ADR-004](adr/ADR-004-three-way-merge.md))
13. **Groups never grant access to lists.** Lists a viewer can't see are omitted.
    ([12-AUTHORIZATION.md](12-AUTHORIZATION.md))
14. **Metadata extraction runs in a PostgreSQL-backed worker** (django-tasks + django-tasks-db),
    with no Redis or Celery. Fetched values are stored apart from user fields.
    ([ADR-008](adr/ADR-008-background-metadata-extraction.md))
15. **Images are re-encoded by Pillow** and served same-origin from a media volume, so the
    strict CSP survives. ([ADR-012](adr/ADR-012-media-and-images.md))
16. **Django stays on 5.2 LTS for V2.** Upgrade to 6.2 LTS after its release (April 2027).
    ([ADR-014](adr/ADR-014-django-version.md))
17. **Git:** the `v2` integration branch, a CI guard against V2 PRs into `main`, and rulesets
    on `main` and `v2`. ([ADR-009](adr/ADR-009-git-v2-integration-branch.md))

## Keeping these documents true

- A PR that changes a documented behaviour updates the document in the same PR.
- A PR that changes a **[Decision]** adds an ADR that supersedes the old one.
- When an **[Open]** question is answered, move it to the decision log in
  [20](20-DECISIONS-AND-OPEN-QUESTIONS.md) and update the affected documents.
