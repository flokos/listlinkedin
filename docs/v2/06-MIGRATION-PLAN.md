# 06: Migration plan (V1 → V2)

## Principles

- **One production cutover.** V2 is built incrementally on `v2` and tested per phase in CI and
  on a V2 staging environment. Production keeps running V1 from `main` until the release PR
  `v2 → main` (roadmap phase 9). Phases are increments of the *codebase*, not of production.
- **Preserve every identifier.** List UUIDs and `public_code`s, link UUIDs, short codes and
  owner token hashes are carried over unchanged. Nothing is regenerated.
- **No invented history.** Each list gets one honest baseline revision.
- **No silent semantic changes.** Expiry dates, visibility and ownership of existing lists stay
  what they are today until their owner changes them.
- **Rehearse, then run.** The full migration runs on a restored copy of production before
  launch, with timings recorded.

## Environments and databases

| Environment | Database | Purpose |
|---|---|---|
| Developer | Local compose volume, disposable | Daily work. `docker compose down -v` resets it |
| CI | Ephemeral, per run | Tests, migration checks, e2e |
| **V2 staging** | Its own PostgreSQL, restored from a production `pg_dump`. It holds the same sensitive data (URLs, titles, token hashes), so it gets production-grade access control | Migration rehearsal, release candidate testing |
| Production | The single production database | Runs V1 until cutover, then V2 |

V1 and V2 never write the same database at the same time [Decision]. There is no
dual-running period, so nothing has to be kept compatible with both codebases.

## Schema and data migrations by phase

Every migration below is a Django migration on `v2`. "Reversible" means Django can unapply it
in development. Production rollback is covered [below](#rollback).

| Phase | Migration | Type | Reversible | Notes |
|---|---|---|---|---|
| 1 | `accounts.0001_initial` (User) + contrib auth, contenttypes, sessions + allauth | schema | yes (empty tables) | **`AUTH_USER_MODEL` is set in the same PR, before any auth migration has ever run.** V1 databases have no auth tables (verified, [01](01-V1-AUDIT.md#models-and-schema-migrations-sharing0001-shortener0001-one-each)), so no "mid-project swap" problem exists [R1] |
| 1 | `sharing.0002_list_ownership` (task 1.3): `owner_id`, `visibility` (V1 rows → `unlisted`, then the default becomes `private`), `description`, `slug` (backfilled, batched), `allow_fork`, `allow_branch`, `creation_key`; `owner_token_hash` and `expires_at` become nullable; CHECKs L2 and L3; `ListMembership`. `tags` (8.1), `head_revision` (3.1), `forked_from_id` (5.1) and `image` (2.3) arrive with their tasks | schema + data | yes (slug backfill: no-op reverse) | Existing rows keep their token hash and `expires_at`; `owner_id` stays NULL (legacy). Covered by `test_migration_ownership.py` |
| 2 | `sharing.0003_link_fields` (task 2.1): link fields (`description`, `icon`, `position`, `deleted_at`, `source_link_id`, `metadata`, `metadata_fetched_at`, `creation_key`) | schema | yes | |
| 2 | `sharing.0004_backfill_link_positions`: backfill `position` per list, `ORDER BY created_at DESC, id DESC` → `0..n-1` | data (batched per list) | no-op reverse | Keeps today's on-screen order (newest first) as the initial manual order |
| 2 | `sharing.0005_link_constraints`: replace the unique (list, URL) constraint with a partial unique index on live links. Add a deferrable unique (list, position), the tombstone CHECK and the live-source unique index | schema | yes | Existing data satisfies all of them (no deleted links exist yet) |
| 2 | `sharing.0006_list_image` (task 2.3): nullable `image` (a media path) on lists | schema | yes | Media files live on the `media` volume, outside the database; unapplying drops only the references |
| 3 | `sharing.0007_head_revision` (task 3.1): `head_revision` (default 0, CHECK `>= 0`). `versioning.0001_initial`: `ListRevision`. `versioning.0002_revision_immutable_trigger` | schema | yes | `0002` let one update through (clearing `created_by_id` on account deletion); `versioning.0004_strict_immutability` (task 3.0) removed it, since user rows are no longer deleted ([ADR-016](adr/ADR-016-account-deletion-grace-period.md)) |
| 3 | `versioning.0003_baseline_revisions`: for every list with `head_revision = 0`, `number = 1`, `kind = 'migrated'`, snapshot of the current state built in SQL; `head_revision = 1` | data (one `INSERT … SELECT` per 500 lists, inside the migration's transaction like `sharing.0004`) | reverse deletes `migrated` revisions and resets those heads to 0 | [Revision initialization](#revision-initialization) |
| 3 | `versioning.0005_baselines_for_new_lists` (task 3.2): the same baseline for lists created between 3.1 and 3.2 (still at head 0) | data | no-op reverse | A no-op on databases that never ran 3.1 without 3.2 |
| 4 | `groups` tables | schema | yes | |
| 5 | `sharing.0008_list_forked_from` (task 5.1): nullable `forked_from_id` (a plain UUID, no FK) on lists | schema | yes | Existing lists are no copies: NULL |
| 5–6 | `ListBranch`, `BranchExclusion`, `SyncRecord`: **postponed** ([ADR-015](adr/ADR-015-postpone-synchronization.md)), not created in V2 | schema | yes | |
| 7 | django-tasks-db tables (app label `django_tasks_database`, task 7.1) | schema (third-party) | yes | Must be unapplied (`migrate django_tasks_database zero`) **before** the package is removed, if the queue is ever replaced ([ADR-008](adr/ADR-008-background-metadata-extraction.md#what-the-database-queue-adds-to-remove-when-switching)) |
| 8 | `pg_trgm` extension, generated search column, GIN indexes | schema | yes | `CREATE EXTENSION` needs the DB owner role. The compose `POSTGRES_USER` is the owner |

All V1 tables are small: lists live at most 30 days and hold at most 100 links. Plain
(non-concurrent) `ALTER TABLE` and index builds take well under a second. **[Assumption]**
Production holds at most tens of thousands of lists. The staging rehearsal records the real
duration. If any step exceeds 10 s, that index is switched to `AddIndexConcurrently`
(non-atomic migration).

Production settings set `statement_timeout=20s` for the API. The `migrate` service must run
with that timeout raised or disabled through an environment override (task 1.1), so a long
data migration fails only on real problems.

## Data mapping

| V1 data | V2 result |
|---|---|
| `SharedList` row | Same row, same `id` and `public_code`. `visibility = unlisted`, `owner_id = NULL` (legacy), token hash kept, `expires_at` kept, `head_revision = 1` |
| `SharedLink` row | Same row, same `id`. `position` from today's order. `description`, `icon` and `source_link_id` NULL. `metadata = {}` |
| `ShortRedirect` row | Unchanged, so every `/r/{code}` keeps resolving |
| Owner tokens (client side) | Unchanged in users' browsers (`ll:owned-lists`) and backup files. They keep working on unclaimed lists |
| Rate-limit cache rows | Unchanged (transient) |
| "Existing metadata" | V1 has none beyond the user's title. After launch, `manage.py backfill_metadata` enqueues fetches for live links of unexpired lists, at most N per minute |

## Revision initialization

V1 never recorded history, so it can't be reconstructed (prompt 11.4). The data migration
writes one revision per list: `number 1`, `kind 'migrated'`, `created_by NULL`, `created_at =
migration time`, snapshot = state at migration. The UI labels it "History starts here (moved
to the new version)". Branch features treat it like any other revision.

## Ownership transition

Product decision: **accounts are required to create lists**
([ADR-011](adr/ADR-011-accounts-required-legacy-lists.md)). Existing lists are **legacy
lists** until claimed or expired.

Options evaluated (prompt 11.3):

| Option | Verdict |
|---|---|
| Claim through verified management credentials | **Chosen.** The token *is* the V1 proof of ownership, it is 256-bit, and it is verified in constant time |
| Keep legacy management temporarily | **Chosen as well.** Unclaimed lists stay manageable with their token until they expire (≤30 days after launch) |
| Nullable ownership during the transition | **Chosen.** `owner_id NULL` *is* the legacy state, guarded by CHECKs L2 and L3 |
| An explicit account-claim operation | **Chosen**: `POST /api/v2/lists/{code}/claim/` |
| Assign owners automatically (by IP, browser, …) | **Rejected.** There's no reliable link between a V1 list and a person, and the prompt forbids arbitrary assignment |

Claim flow:

1. The user signs in. The SPA finds tokens in `localStorage` ("Saved lists") or receives one
   from an edit link or backup file.
2. The SPA offers "Add to my account", per list or all at once.
3. `POST …/claim/` with `Authorization: Bearer <token>` and the session (CSRF). Server, in one
   transaction under the list lock: the list must be unclaimed and unexpired; the token must
   verify in constant time; then `owner_id = user`, `owner_token_hash = NULL`. Visibility
   (`unlisted`) and `expires_at` don't change. Throttled as an owner write. The log line holds
   the list id and user id, never the token.
4. Afterwards the token is dead: v1 and v2 writes with it get 403. The SPA removes it from
   `localStorage` and explains that the list is now in the account.
5. The SPA then offers, without pre-selecting anything, "Keep this list permanently?", which
   removes the expiry. Expiry is never removed silently (prompt 11.5).

Security: a stolen token lets the thief claim the list first. That's the same power the token
grants in V1 (full control, rotation), so claiming adds no new risk. The mitigation is
unchanged: rotate leaked tokens. A second claim attempt by anyone gets 403 because the token
is retired. A repeated claim by the owner returns 200 idempotently.

## Expiration policy

| Lists | Policy |
|---|---|
| Migrated legacy lists | Keep `expires_at` exactly. They expire and are purged as in V1 unless claimed and explicitly made permanent |
| Claimed lists | Keep `expires_at` until the owner changes it. A permanent list must be chosen explicitly |
| New V2 lists | Permanent by default (`expires_at NULL`). The owner can set an expiry date |
| Expired lists (any) | 410 from `expires_at` on, purged by `cleanup` (V1 semantics). Children of an expired parent survive ([08](08-SYNCHRONIZATION-SPEC.md#deletions-expiry-and-restoration)) |

This doesn't convert temporary lists into permanent ones or the other way round (prompt 11.5).
Because new lists default to permanent, the 30-day rule stops being a product promise. The
copy changes accordingly ([11](11-UI-UX-MIGRATION.md)).

## Frontend transition

The V2 SPA replaces the V1 SPA at cutover (the same nginx image build). Continuity:

- `/l/{code}`, `/r/{code}` and `/l/{code}/manage#t=` keep working.
- `ll:owned-lists` in `localStorage` is still read. "Saved lists" becomes the "On this
  device" section of **My lists**, with claim actions. Backup restore accepts `version: 1`
  files until the legacy sunset.
- Users on a stale tab after the deploy get V1's existing stale-chunk reload.

## Deployment strategy (release day)

1. Freeze `main` (V1) except emergency fixes. The release PR `v2 → main` is approved and CI is
   green.
2. Tag the last V1 commit `v1.0.0` and create branch `release/v1` from it, so V1 stays
   buildable and fixable ([16](16-GIT-WORKFLOW.md#releasing-v2)).
3. Rehearse on staging with a fresh production dump. Record durations. Run the full e2e suite
   against staging.
4. **Maintenance window:** nginx serves a static maintenance page (503). Stop `api` and
   `cleanup`. Run `pg_dump -Fc` and verify that it restores.
5. Merge the release PR. Build the images. Run `migrate` (one-shot, as in V1).
6. Start `api`, `worker` and `cleanup`. Run `deploy/smoke-test.sh` plus a V2 smoke checklist
   (sign up, create, legacy edit link, claim, `/r/` redirect).
7. Remove the maintenance page. Watch logs, error rates and the task queue for 48 h (the
   rollback window).

## Rollback

| Level | Possible? | How |
|---|---|---|
| **Application rollback within V2** (a bad V2 build after launch) | Yes | Redeploy the previous V2 images. After launch, V2 migrations follow expand/contract (additive first, removals in a later release), so the previous image works on the newer schema |
| **Schema rollback V2 → V1** | Only inside the rollback window, and only by restoring the backup | Django can unapply most migrations in development, but production data created by V2 (users, owned lists, revisions, groups, tombstones) has no V1 representation. Unapplying would destroy it, and the baseline data migrations aren't meaningfully reversible. Not used in production [Decision] |
| **Data recovery** | Yes | The pre-cutover `pg_dump` (step 4) plus regular backups afterwards. Recommendation: daily `pg_dump` kept 14 days, and WAL archiving (PITR) if the deployment allows it ([14](14-INFRASTRUCTURE.md#backups)) |
| **Returning users to V1** | Inside the rollback window | Maintenance page → restore the pre-cutover dump into a fresh volume → deploy `release/v1` images → remove the page. **Writes made in V2 since cutover are lost**, so communicate it. After the window, fix forward only |

V1 and V2 share Git history but **not** a reversibly shared database. The rollback guarantee
is the backup, not the migrations (prompt 11.7).

## After launch: contracting the legacy path

When `max(expires_at)` of all legacy lists plus 24 h (the purge lag) has passed (roadmap task
9.6):

1. Remove the `/api/v1/` routes and the legacy bearer principal.
2. Drop `owner_token_hash` in a later release (contract step). Drop the backup and restore UI
   and the edit-link route. Keep `/l/{code}/manage` as a redirect to `/l/{code}`.
3. Tighten CHECK L2 to `owner_id IS NOT NULL` (and drop L3).
