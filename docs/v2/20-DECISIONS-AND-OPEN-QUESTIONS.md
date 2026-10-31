# 20: Decisions and open questions

## Decision log

Settled decisions, with where each is justified. Changing one needs a superseding ADR
(CLAUDE.md).

| # | Decision | Decided by | Reference |
|---|---|---|---|
| D1 | V1 stays on `main`; V2 is built on the long-lived `v2` branch; all V2 PRs target `v2` | prompt + planning | [ADR-009](adr/ADR-009-git-v2-integration-branch.md) |
| D2 | Push `v2` and protect `main` and `v2` with rulesets (admin bypass in PR mode); a CI guard on `v2` against PRs into `main` | **user (2026-10-28)** | [16](16-GIT-WORKFLOW.md) |
| D3 | **Accounts are required to create lists**; V1 lists stay manageable with their edit link until claimed or expired | **user (2026-10-28)** | [ADR-011](adr/ADR-011-accounts-required-legacy-lists.md) |
| D4 | Keep `SharedList`/`SharedLink`; no `WebApp` entity | prompt + planning | [ADR-001](adr/ADR-001-preserve-list-and-link.md) |
| D5 | Modular monolith; pure core only for merge, snapshots and policy | planning | [ADR-002](adr/ADR-002-modular-monolith.md) |
| D6 | Immutable full JSONB snapshots | prompt preference, confirmed | [ADR-003](adr/ADR-003-immutable-revision-snapshots.md) |
| D7 | Three-way merge, branch-level baseline, all items decided per apply | planning | [ADR-004](adr/ADR-004-three-way-merge.md) |
| D8 | Child order preserved, parent additions appended, integer positions with move ops | prompt preference, confirmed | [ADR-005](adr/ADR-005-child-ordering-policy.md) |
| D9 | Keep V1 codes; codes as columns and `ShortRedirect` for links; `/g/` for groups; EXTERNAL_URL deferred | planning | [ADR-006](adr/ADR-006-url-shortening-strategy.md) |
| D10 | Custom user in a new `accounts` app; session + CSRF; allauth headless | planning | [ADR-007](adr/ADR-007-authentication-and-ownership-migration.md) |
| D11 | Metadata via django-tasks + django-tasks-db worker; field provenance; SSRF-safe fetcher | planning | [ADR-008](adr/ADR-008-background-metadata-extraction.md) |
| D12 | `/api/v2/` with ViewSets; `/api/v1/` kept for the transition | planning | [ADR-010](adr/ADR-010-viewsets-and-api-v2.md) |
| D13 | Media re-encoded by Pillow, served same-origin | planning | [ADR-012](adr/ADR-012-media-and-images.md) |
| D14 | Soft-delete links only; hard-delete lists and groups | planning | [ADR-013](adr/ADR-013-soft-delete-links-only.md) |
| D15 | Django 5.2 LTS through V2 launch; 6.2 LTS afterwards | planning | [ADR-014](adr/ADR-014-django-version.md) |
| D16 | New lists default to `private`; V1 lists become `unlisted` | planning | [12](12-AUTHORIZATION.md#visibility) |
| D17 | Slugs are cosmetic (`/l/{code}/{slug}`), never identifiers | planning | [09](09-API-DESIGN.md#urls-and-slugs) |
| D18 | Group roles never grant list access; hidden lists omitted entirely | prompt + planning | [12](12-AUTHORIZATION.md) |
| D19 | Revision history visible to editors and owners only | planning | [12](12-AUTHORIZATION.md#list-permission-matrix) |
| D20 | `public` visibility requires a verified email | planning | [13](13-SECURITY.md) |
| D21 | One production cutover at release; no dual-running of V1 and V2 on one database | planning | [06](06-MIGRATION-PLAN.md) |
| D22 | Grid (tiles) by default, with V1's row layout kept as "List" view | planning | [11](11-UI-UX-MIGRATION.md#list-page) |
| D23 | No Pinia; keep the composable singletons until a stated trigger | planning | [10](10-FRONTEND-ARCHITECTURE.md#state-management) |
| D24 | Drag-and-drop with vue-draggable-plus plus a mandatory ⋮ Move alternative | planning | [10](10-FRONTEND-ARCHITECTURE.md#drag-and-drop) |
| D25 | **Synchronization is postponed**: no synced copies, merges or sync UI in the V2 release; forks stay; the design is kept | **user (2026-10-29)** | [ADR-015](adr/ADR-015-postpone-synchronization.md) |
| D26 | **Account deletion has a 30-day grace period**: hidden and signed out at once, restorable by signing in, then erased by a daily job; the anonymous row stays for revision authorship | **user (2026-10-29)** | [ADR-016](adr/ADR-016-account-deletion-grace-period.md) |
| D27 | **No Celery in V2; a later move stays possible**: the worker keeps one enqueue point, thin task wrappers and all state in PostgreSQL, so Celery could replace the database queue after V2 with a superseding ADR | **user (2026-10-30)** | [ADR-008](adr/ADR-008-background-metadata-extraction.md#moving-to-celery-later) |
| D28 | **A page's preview image (`og:image`) is fetched and stored, not shown**: once per link, again when its URL changes or on a manual refresh, through the image pipeline (512 px); showing it waits for Q16. Page thumbnails stay postponed | **user (2026-10-30)** | [13](13-SECURITY.md#ssrf-safe-fetcher), [ADR-008](adr/ADR-008-background-metadata-extraction.md) |
| D29 | **Moderation at launch: operator commands and a report button**, answering Q10. Anyone who can see a list or group, except its owner, can report it; the report emails `MODERATION_EMAIL`. The operator unpublishes, deletes, finds links to a host and suspends accounts with management commands. No Django admin | **user (2026-10-30)** | [13](13-SECURITY.md#moderation), [12](12-AUTHORIZATION.md#operator-actions) |
| D30 | **Group positions keep their gaps**, answering Q17: removing a list leaves a gap that the group's next write closes; the API numbers entries after ordering, so nobody sees gaps. No trigger | **user (2026-10-30)** | [04](04-DOMAIN-MODEL.md#invariants) |
| D31 | **Backups and monitoring are host scripts, not services**: `deploy/backup.sh`, `deploy/restore.sh` and `deploy/autoheal.sh` run from the host's cron or systemd timers, so the stack gains no container and needs no ADR. Alerts go through any command the operator names (`ALERT_COMMAND`) | phase 9 plan, approved by the **user (2026-10-30)** | [14](14-INFRASTRUCTURE.md#backups), [docs/deployment.md](../deployment.md#monitoring) |
| D32 | **V2 is released on GitHub; V1 was never deployed.** There is no production V1 database, so no legacy lists or edit links exist outside development. Task 9.5 pins V1 (`v1.0.0`, `release/v1`, a GitHub Release), merges `v2` into `main`, tags `v2.0.0` and publishes its GitHub Release. A first deployment is a fresh V2 install ([deployment](../deployment.md#first-deploy)). The V1 → V2 [runbook](06-MIGRATION-PLAN.md#runbook) and [22](22-RELEASE-REHEARSAL.md) stay as the record that the migrations work, and as the path for anyone running V1 from `release/v1`. The legacy sunset (9.6) follows `v2.0.0` as `v2.1.0`, without the 30-day wait: no legacy list can still be alive | **user (2026-10-31)** | [06](06-MIGRATION-PLAN.md#runbook), [17](17-IMPLEMENTATION-ROADMAP.md) |
| D33 | **Runtime upgrades go one supported step at a time, as planned PRs.** Python moves to the next version that Django supports (3.13 → 3.14; 3.15 waits for Django), Node from one LTS line to the next (24 → 26; odd releases are never LTS and are out of support within months), and `@types/node` follows the Node that runs the code (26 for the app, 24 for the e2e image's Node). Dependabot's major-version jumps (#47–#51) are judged against this, and `dependabot.yml` ignores versions outside it | **user (2026-10-31)** | [ADR-014](adr/ADR-014-django-version.md) |

## Open questions

Each has a recommendation, so work isn't blocked. Owners decide before the task named.
After the release the open ones are product questions for later versions. The first to plan is
Q16 (link pictures), then the "after launch" rows as usage data arrives; Q15 decides whether
phase 6 resumes.

| # | Question | Recommendation | Decide before |
|---|---|---|---|
| Q1 | Should `public` lists and groups become indexable by search engines (drop `noindex` for them)? | Keep `noindex` for the MVP. Indexing needs server-rendered metadata (the SPA has none) and invites abuse. Revisit after launch | 8.2 |
| Q2 | Revision retention: keep every revision forever? | Yes for the MVP (bounded by the link cap). Add "keep the last N + daily for 90 days" only if storage grows | after launch |
| Q3 | Default link cap: stay at 100? | Keep 100 (a setting). Raising it affects snapshot size, preview UX and the merge timing targets. Re-measure first | 2.1 |
| Q4 | Invitations for people without an account (email invite links)? | Later enhancement. MVP adds existing accounts by email | 1.5 |
| Q5 | Ownership transfer between accounts? | Later enhancement (owner → existing editor, confirmed by both) | after launch |
| Q6 | Social login or MFA? | Not in the MVP. allauth supports both, so add them by configuration later | after launch |
| Q7 | Trash / undo for deleted lists? | Not in the MVP ([ADR-013](adr/ADR-013-soft-delete-links-only.md)). If wanted, a separate `deleted_lists` archive table (snapshot + metadata) avoids soft-delete filters everywhere | after launch |
| Q8 | Where will V2 be hosted, and does it have an SMTP relay? | Same single-host compose deployment as V1, with any SMTP relay. Needed by 1.2 for production-like testing | 1.2 |
| Q9 | Is there production V1 data today, and how much? | **Answered (D32, 2026-10-31): none.** V1 was never deployed. The migration was still rehearsed with 20,001 V1 lists ([22](22-RELEASE-REHEARSAL.md)) | 9.5 |
| Q10 | Moderation tooling beyond management commands (Django admin, report button)? | **Decided (D29, 2026-10-30):** management commands and a report button, built in task 9.0. No Django admin | 9.0 |
| Q11 | Per-field merge choices and partial merges? | Deferred. Revisit with real usage data from merge logs | after launch |
| Q12 | Should a public group show an "N private lists hidden" hint to its *editors*? | Editors see the per-entry notice ([12](12-AUTHORIZATION.md#which-lists-a-group-shows-to-a-viewer)). Never shown to visitors | 4.3 |
| Q13 | Add a PR template and a short V1 CLAUDE.md to `main`? | Optional V1 docs PR ([16](16-GIT-WORKFLOW.md#optional-pr-template-for-main)). It helps contributors who start from `main` | anytime |
| Q14 | Upgrade path to Django 6.2 LTS: when? | A dedicated project after V2 is stable, before April 2028 (5.2's end of support) | after launch |
| Q15 | Synchronization: what model, if any? Keep the reviewed three-way merge of [08](08-SYNCHRONIZATION-SPEC.md), simplify it, or drop synced copies | Decide with the product owner; record it in a new ADR before resuming phase 6 | resuming phase 6 |
| Q16 | Link pictures: should a link's picture be a pre-generated thumbnail of its page, or else a ready-made image for well-known sites or kinds of link (for example email links)? | **Postponed by the user (2026-10-29) until the rest of the app is done.** Meanwhile each page's own preview image (`og:image`) is fetched and stored but not shown (D28), so it is there if Q16 settles on it. Open points then: page thumbnails need a page renderer (headless browser or a third-party service), which [02](02-PRODUCT-REQUIREMENTS.md#metadata-9) currently defers and which would run inside the SSRF-safe worker; ready-made images need a curated set and matching rules; email links would first need a new link type, since links are http/https only today. Any image still goes through the media pipeline ([ADR-012](adr/ADR-012-media-and-images.md)) | after V2 is complete |
| Q17 | Group positions: keep them as plain sort keys, where deleting a list can leave a gap that the group's next write closes, or keep them strictly `0..n-1` with a trigger on `groups_grouplist` deletes that shifts later entries down? | **Decided (D30, 2026-10-30): keep the gaps** (G1 in [04](04-DOMAIN-MODEL.md#invariants)). The API numbers entries after ordering, so nobody sees them | 9.0 |

## Final architectural review (prompt Step 12)

| Perspective | Assessment |
|---|---|
| Backend maintainability | V1's structure is kept. New apps have clear ownership. A pure core sits where the risk is. Services grow into packages only when needed |
| Domain correctness | Invariants are numbered and mapped to tests. The merge is fully specified, including 16 added scenarios. Baselines and idempotency are explicit |
| Database integrity | Invariants are enforced by constraints and triggers where possible: CHECKs for legacy lists, partial uniques, deferrable positions, revision immutability |
| Frontend maintainability | The same stack and patterns. The largest view gets split. Types are generated from OpenAPI. Two new dependencies |
| User experience | Product language replaces Git terms. V1 workflows are preserved (create, add, edit, share, copy short URL, view, manage), with tiles and a list view |
| Security | The threat model covers every prompt item. SSRF is isolated to the worker. Uniform 404s. CSRF is introduced correctly. Media is re-encoded |
| Performance | Targets are set, query counts are tested, the cap bounds the merge cost. No speculative caching |
| Infrastructure simplicity | One new service (worker) and one new volume (media). No Redis or Celery |
| Migration safety | Identifiers are preserved, history is honest, a rehearsal is planned, and the backup-based rollback is stated plainly |
| Testability | Engine properties, a matrix-driven authorization suite, real concurrency tests, and a V1 regression checklist |

The main residual risk is sync UX complexity. It is mitigated by the decision defaults, the
explicit sections, and the deferred list.
