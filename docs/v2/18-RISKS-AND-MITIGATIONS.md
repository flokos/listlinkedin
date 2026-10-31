# 18: Risks and mitigations

Likelihood (L) and Impact (I) are rated **H**igh, **M**edium or **L**ow, and the table is
sorted by priority. P1 risks have a dedicated test suite *and* a design control. P3 risks are
watched, not engineered against. Rows 1–30 are the prompt's list (Part 19) under its original
numbers. Rows 31–35 were added by this planning.

> Risks 11–15 and 35 concern synchronization. They are **dormant** while it is postponed
> ([ADR-015](adr/ADR-015-postpone-synchronization.md)) and come back when it is resumed.

## P1: critical

| # | Risk | L | I | Mitigation | Validation |
|---|---|---|---|---|---|
| 13 | Lost local modifications in a sync | M | H | The child is changed only by explicit decisions. ACCEPT touches only parent-changed fields. Undecided items block apply ([08](08-SYNCHRONIZATION-SPEC.md#decisions)) | properties 3 and 4, scenarios 7–9 and 11 ([15](15-TEST-STRATEGY.md#unit-tests-pure-domain)) |
| 14 | Incorrect synchronization baselines | M | H | Base moves only on a successful apply, to the exact parent revision in the fingerprint. Every item must be decided | scenario 17 test, property 4, baseline worked example |
| 15 | Duplicate links after repeated merges | M | H | Idempotency key + `SyncRecord`; fingerprint invalidation; a unique live source per child; the URL guard and adopt rule | concurrency tests (same and different keys), property 7, scenario 31 |
| 8 | Private-data leakage through groups | M | H | Per-viewer SQL filtering, entries omitted with no placeholders or counts, the add-list share rule ([12](12-AUTHORIZATION.md#which-lists-a-group-shows-to-a-viewer)) | group leak matrix tests, e2e scenario 5 |
| 7 | Permission escalation | M | H | A single pure policy, owner-only settings and members, authorization re-checked under the lock | parametrized matrix tests, escalation attempts |
| 20 | SSRF through metadata fetching | M | H | Fetching only in the worker; resolve-validate-pin; manual redirects; ports 80/443; limits; optional egress firewall ([13](13-SECURITY.md#ssrf-safe-fetcher)) | fetcher tests incl. DNS rebinding and redirects to private ranges |
| 3 | Data loss in the database migration | L | H | Additive migrations; staging rehearsal on a production dump; `pg_dump` at cutover; a migration test on V1-shaped data | the migration test (task 1.3, 2.1, 3.1), rehearsal report (9.5) |
| 4 | Breaking V1 short URLs or edit links | L | H | Codes and ids preserved. `/l`, `/r` and `/l/…/manage` keep working. Tombstones keep redirect rows | V1 tests kept; e2e legacy journey; the post-migration smoke list |
| 9 | Revisions inconsistent with lists | M | H | A revision is written in the mutation's transaction under the lock; no-op detection; R4 | R4 property test, forced-failure test |

## P2: high

| # | Risk | L | I | Mitigation | Validation |
|---|---|---|---|---|---|
| 5 | Authentication migration failures | M | M | `AUTH_USER_MODEL` set before any auth migration (V1 has no auth tables). allauth, not custom auth code | 1.1 migration and auth tests on a V1 dump |
| 6 | Unauthorized ownership claims | L | H | Token proof + session, under the lock, token retired, throttled; never automatic | claim tests: wrong, expired, claimed, double |
| 10 | Concurrent revisions with duplicate numbers | L | M | Numbering under the row lock plus UNIQUE (list, number) | 20-writer concurrency test |
| 11 | Branch ancestry corruption | L | H | `ListBranch` rows only created with new children; UNIQUE child; SET NULL on parent deletion with `parent_deleted_at` | model tests, deletion tests |
| 12 | Cyclic branch relationships | L | H | Impossible by construction (no re-parenting) plus CHECK parent ≠ child | test that no API exposes re-parenting; constraint test |
| 16 | Incorrect deletion handling | M | M | Explicit table of deletion semantics ([05](05-DATABASE-DESIGN.md#deletion-semantics)); hard delete only for lists and groups | deletion tests per row of that table |
| 17 | Restoring deleted links incorrectly | M | M | Revival by `id` (same row and short code); tombstone-then-revive ordering in restore | restore tests (07 #5), scenario 11 |
| 19 | Background metadata overwriting manual edits | M | M | Field provenance (`metadata` separate from user fields); conditional update on the URL | metadata race concurrency test |
| 21 | Malicious redirects / open redirect | L | H | `/r/` only to stored validated URLs; denylist re-checked at redirect time; `next` validation | V1 redirect tests + `next` tests |
| 1 | Accidental changes to `main` | L | H | Rulesets on `main` (PR + `checks` required, no force-push or deletion), CLAUDE.md rules | verified by `gh api …/rules/branches/main` (task 0.3) |
| 2 | V2 PRs targeting `main` | M | M | `gh-merge-base` / `--base v2`, the CI guard (blocking through the required `checks`), CLAUDE.md | the guard's shell logic tested locally in 0.3; visible on any wrong PR |
| 33 | Phishing or abuse via public lists and the directory | M | M | Verified email required for `public`; denylist; `noindex`; since 9.0 a report button that emails the operator, and operator commands to unpublish, delete, find links to a host and suspend accounts ([13](13-SECURITY.md#moderation)) | gate tests; report and command tests; e2e `report.spec.ts` |

## P3: medium and low

| # | Risk | L | I | Mitigation | Validation |
|---|---|---|---|---|---|
| 18 | Parent expiration with active children | M | L | Children are independent copies; status `parent_expired` then `parent_deleted`; cleanup sets `parent_deleted_at` | cleanup + sync status tests |
| 22 | Broken mobile drag-and-drop | M | M | Spike on the phone projects; the ⋮ Move menu always works | e2e scenario 4 on mobile-safari and mobile-chrome. Since 2.5: touch drag verified on mobile-chrome; iOS touch drag can't be automated, so it is in the 9.3 manual pass ([10](10-FRONTEND-ARCHITECTURE.md#drag-and-drop)) |
| 23 | Inaccessible conflict-resolution UI | M | M | Radio groups with legends, text plus colour, focus management, manual screen-reader QA | axe, keyboard spec, QA checklist (9.3) |
| 26 | N+1 queries | M | L | Annotated querysets, prefetching, query-count assertions | `tests/test_query_counts.py` (since 9.2): every read endpoint measured small and at the target sizes, equal counts within budget |
| 27 | Excessively large snapshots | L | L | 100-link cap; JSONB TOAST compression; measured in 9.2: 5.4 KiB stored for a typical 100-link list, 322 KiB at worst (every field at its maximum, incompressible) | snapshot size test at the cap (`tests/test_query_counts.py`) |
| 28 | Stale frontend state | M | M | `ETag`/`If-Match`, revalidate on view, reload on 409/412, no optimistic success for merges | e2e state tests |
| 29 | Inconsistent API error handling | M | L | One domain-error mapping table; machine `code`s; DRF shapes kept | error-shape tests per endpoint |
| 30 | Incomplete regression coverage | M | M | The V1 regression checklist; V1 tests never deleted for failing | CI. Checklist reviewed in 9.1 ([21](21-SECURITY-REVIEW.md#v1-regression-checklist): every named test still runs) |
| 31 | Young dependencies (django-tasks-db is beta; allauth headless is newer than core allauth) | M | M | Exact pins; the fallback design for the queue (~100 lines); allauth is widely used and actively released [R6]. Since 7.1: the gaps found in the library's source (no retries, no heartbeat, no recovery of tasks a dead worker left running) are covered by our own retry helper, `check_worker` and `recover_stuck_tasks` ([ADR-008](adr/ADR-008-background-metadata-extraction.md#verified-in-task-71)) | worker tests; upgrade PRs read changelogs |
| 32 | Email deliverability (verification and reset) | M | M | Verification is optional for private use; verified email is required only for `public` and invitations; standard SMTP relay | e2e with Mailpit; production smoke |
| 34 | CSRF misconfiguration breaks the SPA or opens CSRF | M | M | Same-origin only; `CSRF_TRUSTED_ORIGINS` from `PUBLIC_BASE_URL`; tests for missing and wrong token | API CSRF tests, e2e flows |
| 35 | Scope creep in the merge UI (per-field picks, partial merges) | M | M | Explicitly deferred list ([08](08-SYNCHRONIZATION-SPEC.md#deferred-explicitly-out-of-scope-for-v2-mvp)) | review checklist on 6.x PRs |
| 24 | Unnecessary infrastructure | L | M | Each service justified in [14](14-INFRASTRUCTURE.md). Any new one needs an ADR (CLAUDE.md) | ADR review |
| 25 | Overengineering | M | M | A pure core only for merge, snapshots and policy; no generic repositories, event bus or CQRS stores ([03](03-ARCHITECTURE.md#why-this-shape)) | PR review against ADR-002 |

## Watch list after launch

- Sync conflict and failure rates (from merge logs): rising conflicts on unchanged fields
  would point to a classification bug.
- Metadata failure rate per error code. Repeated `blocked_address` hits for one user suggest
  someone is probing.
- 404 rate on `/r/` and `/l/`: enumeration attempts or broken migrations.
- Legacy lists remaining unclaimed vs expired, which feeds the timing of the sunset task 9.6.
