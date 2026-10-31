# 02: Product requirements

Every feature from the V2 prompt is listed here with a class:

- **MVP**: required for the V2 release (`v2 → main`).
- **Later**: wanted, designed not to be blocked, but scheduled after the release.
- **Deferred**: deliberately not built. The reason is given.

The prompt section is in brackets. Nothing from the prompt is omitted. If you find a missing
item, add it here.

## Product summary

V2 turns anonymous 30-day link lists into a collaborative platform for organizing, sharing and
synchronizing collections of links. People sign up, own lists, choose who sees them, arrange
lists into group workspaces, keep a version history, make copies that stay in sync with their
source (**postponed**, [ADR-015](adr/ADR-015-postpone-synchronization.md)), and discover public collections. **A List contains Links** stays the core concept.

## Preserved V1 capabilities [4.1, 8.1]

| Capability | Class | V2 form |
|---|---|---|
| Create a collection | MVP | Signed-in users only ([ADR-011](adr/ADR-011-accounts-required-legacy-lists.md), user decision) |
| Add, edit, remove links | MVP | Tiles and list view; editors and owners |
| Share a collection through a URL | MVP | `/l/{code}` unchanged; visibility chosen in the Share dialog |
| URL shortener, copy short URLs | MVP | `/r/{code}` unchanged, visibility-aware |
| Stable collection identifiers | MVP | `id` and `public_code` preserved forever |
| Creator-controlled management | MVP | Owners and roles. V1 edit links worked for unclaimed V1 lists until v2.1.0 |
| Anonymous access to shared collections | MVP | Anonymous viewing of `unlisted` and `public` lists |
| Temporary collections | MVP | Optional expiry. V1 lists keep their dates |
| No mandatory accounts | **Changed** | Viewing needs no account; creating does (user decision, 2026-10-28) |
| Dockerized development | MVP | Unchanged; adds a worker service |
| DRF ViewSets, business logic separate from the API | MVP | `/api/v2/` ViewSets ([ADR-010](adr/ADR-010-viewsets-and-api-v2.md)) |
| Client-side search and sort inside a list | MVP | Kept, plus "Custom order" |
| Edit-link backup and restore, token rotation | MVP (legacy only) | Removed in the legacy sunset (task 9.6, v2.1.0) |

## Accounts and access [5.1, 5.6, 8.8]

| Requirement | Class | Notes |
|---|---|---|
| User accounts (sign up, sign in, sign out) | MVP | Email + password via django-allauth headless |
| Email verification, password reset | MVP | Verification is required for making things public and for adding members |
| Account management (display name, password, email change, delete account) | MVP | |
| Users own many lists and groups | MVP | `owner_id` |
| Roles OWNER / EDITOR / VIEWER on lists and groups | MVP | [12](12-AUTHORIZATION.md) |
| Permission rules: view, create, edit, delete, share, manage members, change visibility, fork, branch, synchronize, restore revisions | MVP (branch and synchronize: **Postponed**, [ADR-015](adr/ADR-015-postpone-synchronization.md)) | Full matrix in [12](12-AUTHORIZATION.md#list-permission-matrix) |
| Collaborator "invitations" | MVP: add an existing account by email. **Later**: email invitations for people without an account | Q4 |
| Access-denied, authentication-required and anonymous-sharing screens | MVP | [11](11-UI-UX-MIGRATION.md#ui-states) |
| Migration from creator management links to accounts (claim) | MVP | [06](06-MIGRATION-PLAN.md#ownership-transition) |
| A share link never grants editing | MVP | Invariant A3 |
| Ownership transfer | Later | Q5 |
| Social login, MFA | Later | Q6 |

## Lists [5.2]

| Requirement | Class | Notes |
|---|---|---|
| Stable `id`; title, description, image, slug, visibility, `allow_fork`, `allow_branch`, `expires_at`, timestamps | MVP | `deleted_at` replaced by hard delete ([ADR-013](adr/ADR-013-soft-delete-links-only.md)) |
| Visibility PRIVATE / UNLISTED / PUBLIC with the stated semantics | MVP | default `private`; V1 → `unlisted` |
| Slug strategy (uniqueness, changes, collisions, reserved names, short URLs) | MVP | Cosmetic, non-unique slugs; the code stays the identifier ([09](09-API-DESIGN.md#urls-and-slugs)) |
| Member of several groups; can exist without a group | MVP | `GroupList` |
| Parent, child, many children, nested | **Postponed** | Branches ([08](08-SYNCHRONIZATION-SPEC.md)), [ADR-015](adr/ADR-015-postpone-synchronization.md) |
| Optional expiry; permanent lists never expire | MVP | |
| Tags | MVP | Used by the directory |
| Trash / undo for deleted lists | Later | Q7 |

## Links [5.3, 8.2, 8.7]

| Requirement | Class | Notes |
|---|---|---|
| `url`, `title`, `description`, `icon`, `position`, `source_link_id`, `metadata`, `metadata_fetched_at`, timestamps, `deleted_at` | MVP | [05](05-DATABASE-DESIGN.md) |
| Changing a URL never creates a new Link; the short URL follows the current value | MVP | Invariant K1 |
| Branch origin tracking through `source_link_id`, which survives the parent row's deletion | MVP | No FK. Recorded on forks; sync use postponed ([ADR-015](adr/ADR-015-postpone-synchronization.md)) |
| Explicit order with drag-and-drop, consistent under concurrency | MVP | Move ops under the lock ([ADR-005](adr/ADR-005-child-ordering-policy.md)) |
| Tiles: 128×128 icon, name, optional description, ⋮ menu (open, edit, remove, reorder, move) | MVP | [11](11-UI-UX-MIGRATION.md#list-page) |
| Grid, list or switchable view | MVP | Switchable; grid default |
| Description available to authorized viewers | MVP | Clamped in the tile; full in Details and list view |
| Move a link to another list | MVP | Copy + tombstone (K4) |
| No separate WebApp entity | MVP constraint | [ADR-001](adr/ADR-001-preserve-list-and-link.md) |
| Accessible drag-and-drop alternative, touch support | MVP | WCAG 2.5.7 ([10](10-FRONTEND-ARCHITECTURE.md#drag-and-drop)) |

## Groups [5.4, 5.5, 8.3]

| Requirement | Class | Notes |
|---|---|---|
| Group with its own visibility, ownership, permissions, tags, sharing URL and metadata | MVP | `/g/{code}` |
| Many-to-many with lists, ordered, unique per group | MVP | |
| A group never duplicates list content | MVP | G2 |
| A public group never bypasses list permissions or leaks existence | MVP | [12](12-AUTHORIZATION.md#which-lists-a-group-shows-to-a-viewer) |
| Workspace with a left sidebar; tablet and mobile adaptations; keyboard navigation; focus management; responsive grid; navigation state persistence | MVP | [11](11-UI-UX-MIGRATION.md#groups-workspace) |

## Revisions [5.7]

| Requirement | Class | Notes |
|---|---|---|
| Immutable full snapshots in PostgreSQL with a schema version | MVP | [07](07-REVISION-SPEC.md) |
| Created atomically with the change; failures create none | MVP | R1 |
| Restore creates a new revision; history never rewritten | MVP | R3, R5 |
| No-op, metadata-only and reorder handling | MVP | [07](07-REVISION-SPEC.md#mutation-rules) |
| Enough information to reconstruct deleted links | MVP | Tombstones + snapshots |
| History UI | MVP | |
| Retention policy | Later | Q2 |

## Branching and synchronization [5.8, 5.9, 6, 8.4, 8.5]

> **Synchronization is postponed** ([ADR-015](adr/ADR-015-postpone-synchronization.md), 2026-10-29): it needs more thinking. Only forks
> ("Make a copy") remain in the V2 release. The rows below keep their original class for
> reference; **Postponed** overrides it.

| Requirement | Class | Notes |
|---|---|---|
| Fork (independent copy) and branch (synced copy), both ordinary lists | MVP for forks; branches **Postponed** | |
| One direct parent; many children; no cycles; nested allowed; sync only with the immediate parent; child survives parent deletion | **Postponed** (was MVP) | B1–B6 |
| Atomic, consistent branch creation | **Postponed** (was MVP); forks: MVP | |
| Three-way diff, conflict detection, field-level merge, the 20 prompt scenarios (+16 added) | **Postponed** (was MVP) | [08](08-SYNCHRONIZATION-SPEC.md#scenario-catalogue) |
| ACCEPT / KEEP_LOCAL / EXCLUDE with defined semantics for additions, edits and deletions | **Postponed** (was MVP) | |
| Persistent, source-keyed exclusions; removable | **Postponed** (was MVP) | |
| Child order preserved; parent additions appended; parent-only reorders not synced (documented) | **Postponed** (was MVP) | |
| Preview without writes, with stable change ids | **Postponed** (was MVP) | |
| Apply: authorized, verified, rejects stale plans, atomic, idempotent, advances the baseline | **Postponed** (was MVP) | |
| Branching UI and merge preview UI (original, parent and child values, no raw JSON) | **Postponed** (was MVP); "Make a copy" UI: MVP | [11](11-UI-UX-MIGRATION.md#merge-preview-get-updates) |
| Per-field choices; partial merges; sync notifications | Later | Q11 |
| Multi-parent merge, re-parenting, parent-order sync, syncing list title and settings, pushing to the parent, automatic sync | **Deferred** | Prompt 1.3 YAGNI and 6 "not Git" |

## Short URLs [5.10]

| Requirement | Class | Notes |
|---|---|---|
| Targets LIST, GROUP, LINK | MVP | `/l/`, `/g/`, `/r/` ([ADR-006](adr/ADR-006-url-shortening-strategy.md)) |
| Target EXTERNAL_URL | **Deferred** | A general-purpose shortener for arbitrary URLs is an open-redirect and phishing magnet with no product need in V2. Revisit with abuse controls |
| Stable across title, slug, content and URL changes; resolve to the current link value | MVP | |
| Never bypasses visibility | MVP | S2 |
| Secure random codes, DB uniqueness, collision retries | MVP | V1 implementation kept |
| Multiple aliases per link | Later | The V1 schema already allows it |

## Metadata [9]

| Requirement | Class | Notes |
|---|---|---|
| Fetch title, description, favicon, Open Graph image and relevant HTML metadata (site name) | MVP | [ADR-008](adr/ADR-008-background-metadata-extraction.md) |
| User overrides; manual entry always works | MVP | Field provenance |
| SSRF protections (every item in prompt 9.2) | MVP | [13](13-SECURITY.md#ssrf-safe-fetcher) |
| Background processing, justified, no RabbitMQ | MVP | PostgreSQL-backed worker |
| A delayed job never overwrites manual edits; retry and failure behaviour | MVP | |
| Browser automation / headless Chromium | **Deferred** | Not needed for HTML metadata (prompt 9.1) |
| Link pictures beyond icons: a pre-generated **thumbnail of the page** the link goes to, or else a **ready-made image** for well-known sites or kinds of link (for example email links) | **Postponed** (user, 2026-10-29) until the rest of the app is done | [Q16](20-DECISIONS-AND-OPEN-QUESTIONS.md#open-questions). Until then a tile shows the uploaded icon, the fetched icon (7.3) or the letter avatar |

## Discovery [10]

| Requirement | Class | Notes |
|---|---|---|
| Public directory of lists and groups | MVP | |
| Search by title and description; tag filters; pagination; sorting | MVP | PostgreSQL FTS + `pg_trgm` |
| Search inside lists | MVP | Client-side, as in V1 |
| Private and unlisted never appear; no leaked metadata | MVP | |
| Search-engine indexing of public pages | Later | Q1 |
| Elasticsearch / OpenSearch | **Deferred** | Not needed at this scale (prompt 10) |

## Cross-cutting [8.6, 8.9, 8.10, 13–15]

| Requirement | Class |
|---|---|
| Every UI state in prompt 8.6 | MVP ([11](11-UI-UX-MIGRATION.md#ui-states)) |
| Reuse the design system; no competing UI library | MVP |
| WCAG 2.2 AA where practical | MVP |
| Test strategy across all levels, V1 regression checklist | MVP ([15](15-TEST-STRATEGY.md)) |
| Threat model and mitigations | MVP ([13](13-SECURITY.md)) |
| Docker-only workflow; modular monolith; justified infrastructure; lightweight observability | MVP ([14](14-INFRASTRUCTURE.md)) |
| Report-abuse button, moderation UI | Later (Q10) |
| Account data export | Later |
| Kubernetes, microservices, event sourcing, distributed CQRS, extra databases, Redis/Celery without need | **Deferred** (prompt 1.3) |
