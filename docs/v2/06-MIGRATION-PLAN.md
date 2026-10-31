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
| 8 | `sharing.0009_discovery` and `groups.0002_discovery` (task 8.1): `pg_trgm` extension, `tags` (empty), generated `search` column, GIN and partial indexes, the tag-count CHECK | schema | yes (verified: unapply and reapply) | `CREATE EXTENSION` needs the DB owner role. The compose `POSTGRES_USER` is the owner. Adding a stored generated column rewrites the table, under a second at V1 sizes |
| 9 | `sharing.0010_directory_title_index` and `groups.0003_directory_title_index` (task 9.2): the title trigram index moves from `title` to `UPPER(title)` | schema (index only) | yes (verified) | Builds the index on the existing rows; quick at V1 sizes |
| 9 | `accounts.0003_user_suspended_at` (task 9.0): nullable `suspended_at` on users, set by the operator's `suspend_account` | schema | yes | Existing accounts aren't suspended: NULL |

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
| "Existing metadata" | V1 has none beyond the user's title. After launch, `manage.py backfill_metadata` (task 7.3) queues fetches for live links of unexpired lists whose metadata doesn't describe their URL, `--limit` per run (default 1000; `--dry-run` counts). The worker paces them: two processes, one request per host per second. Safe to run again |

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

The outline: freeze V1, pin it, rehearse on a copy of production, then a maintenance window
in which V1 stops, the database is dumped, V2 migrates and starts, and is checked; then a
48-hour watch during which a rollback to V1 is possible. Rehearsed in task 9.5 with
[deploy/rehearse-release.sh](../../deploy/rehearse-release.sh): every step below and the
rollback, with timings, in [22](22-RELEASE-REHEARSAL.md).

### Runbook

**V1 was never deployed (D32 in [20](20-DECISIONS-AND-OPEN-QUESTIONS.md)), so this project
has no cutover:** its first deployment is a fresh V2 install
([deployment](../deployment.md#first-deploy)). The runbook stays as the rehearsed path for
anyone running V1 from `release/v1`. It needs a V2 release that still has the legacy path
(`v2.0.x`; 9.6 removes it in `v2.1.0`). Its git steps are done: check out the V2 tag and
start at step 3. It assumes V1 runs from a checkout of `main` in
`/srv/listlinkedin` (compose project `listlinkedin`, `.env` next to `compose.prod.yaml`).
`dc` stands for `docker compose -f compose.prod.yaml`.

**Before the day**

1. Pin V1 ([16](16-GIT-WORKFLOW.md#releasing-v2)): tag `v1.0.0` on `main` (`fb5f901`) and
   create `release/v1` from it. Check that both exist on GitHub. Open the release PR
   `v2 → main`, and wait for CI to pass. Don't merge it yet.
2. Rehearse on a copy of production. On a machine allowed to hold its data, run
   `bash deploy/rehearse-release.sh v1-prod.dump`, with the dump made by `dc exec -T db sh -c
   'pg_dump -Fc -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > v1-prod.dump` on the server. It
   must pass. Note the `migrate` time: it sets the window.
3. Add V2's settings to `.env` ([deployment](../deployment.md#configuration)):
   - the SMTP relay (`EMAIL_*`);
   - `MODERATION_EMAIL` and `DEFAULT_FROM_EMAIL`, if wanted.

   V1 sent no mail, so these are new. Announce the window and the end of edit links for new
   lists.

**The window** (rehearsed: about a minute of downtime at 20,000 lists; plan 30 minutes)

```bash
cd /srv/listlinkedin && alias dc='docker compose -f compose.prod.yaml'
# 4. Keep V1's images: V2 builds the same names, and a rollback then needs no rebuild.
docker tag listlinkedin:prod listlinkedin:v1 && docker tag listlinkedin-nginx:prod listlinkedin-nginx:v1
# 5. Merge the release PR (merge commit) and tag v2.0.0 on main, then build V2 while V1 serves.
git fetch --tags && git checkout v2.0.0
dc build
# 6. Maintenance page: V2's nginx replaces V1's and answers 503 to everything.
touch deploy/maintenance/on
dc up -d --no-deps nginx
curl -sI https://<host>/ | head -1                      # HTTP/2 503
# 7. Stop V1 and take the pre-cutover dump (keep it off the server too).
dc stop api cleanup
dc exec -T db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > /var/backups/listlinkedin/pre-v2.dump
dc exec -T db pg_restore --list < /var/backups/listlinkedin/pre-v2.dump > /dev/null && echo dump OK
# 8. Migrate and start V2 (migrate runs first; the others wait for it).
dc up -d --wait
dc logs migrate | tail -5
dc exec api python manage.py check --deploy
dc ps                                                   # api and worker: healthy
# 9. End the maintenance page.
rm deploy/maintenance/on
```

10. **Check in a browser** (the V2 smoke checklist):
    - sign up and confirm the email that arrives;
    - create a list, add a link, and watch its title and icon appear;
    - open its short URL;
    - open an old list's address and an old short URL;
    - from a device that holds an edit link, edit that list, then claim it with **Add to my
      account**;
    - report a public list and check that `MODERATION_EMAIL` receives it.

    If anything essential fails, [roll back](#returning-to-v1).
11. **Fetch details for V1's links**, in batches. Don't raise `--limit`: tasks that wait over
    10 minutes make the worker unhealthy
    ([22, finding 4](22-RELEASE-REHEARSAL.md#findings)). Run it in `tmux` or with `nohup`. It
    stops when a run queues nothing:

    ```bash
    manage() { docker compose -f compose.prod.yaml exec -T api python manage.py "$@"; }
    while ! manage backfill_metadata | grep -q '^Queued 0 '; do
        until manage check_worker | grep -q 'Task queue OK: 0 ready'; do sleep 60; done
    done
    ```

12. **Schedule** [backups and autoheal](../deployment.md#backups) with cron. V1 had neither.

**The 48-hour watch** (the rollback window). Watch:

- the autoheal alerts;
- `dc logs --since 1h api worker` for errors;
- `dc exec worker python manage.py check_worker`;
- `/healthz` from outside.

After 48 hours, roll forward only. Delete `listlinkedin:v1` and `listlinkedin-nginx:v1` once
V2 is trusted.

### Returning to V1

Possible only inside the window. Everything written in V2 since the cutover is lost, so tell
people. The rehearsal took 19 s plus the checks.

```bash
cd /srv/listlinkedin && alias dc='docker compose -f compose.prod.yaml'
touch deploy/maintenance/on                             # V2's nginx shows the page
dc stop api worker cleanup
dc exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --force "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
dc exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --exit-on-error' < /var/backups/listlinkedin/pre-v2.dump
git checkout release/v1
docker tag listlinkedin:v1 listlinkedin:prod && docker tag listlinkedin-nginx:v1 listlinkedin-nginx:prod
dc up -d --no-build --remove-orphans --wait            # V1's services; V2's worker is removed
curl -s https://<host>/healthz
```

V1's nginx has no maintenance page, so the site is back once the last command finishes.
The `media` volume stays and V1 ignores it. Keep `main` as it is and fix V2 forward, then
release again.

## Rollback

| Level | Possible? | How |
|---|---|---|
| **Application rollback within V2** (a bad V2 build after launch) | Yes | Redeploy the previous V2 images. After launch, V2 migrations follow expand/contract (additive first, removals in a later release), so the previous image works on the newer schema |
| **Schema rollback V2 → V1** | Only inside the rollback window, and only by restoring the backup | Django can unapply most migrations in development, but production data created by V2 (users, owned lists, revisions, groups, tombstones) has no V1 representation. Unapplying would destroy it, and the baseline data migrations aren't meaningfully reversible. Not used in production [Decision] |
| **Data recovery** | Yes | The pre-cutover `pg_dump` (step 4) plus regular backups afterwards. Recommendation: daily `pg_dump` kept 14 days, and WAL archiving (PITR) if the deployment allows it ([14](14-INFRASTRUCTURE.md#backups)) |
| **Returning users to V1** | Inside the rollback window | Maintenance page → restore the pre-cutover dump → run the kept V1 images from `release/v1` ([commands](#returning-to-v1), rehearsed in [22](22-RELEASE-REHEARSAL.md)). **Writes made in V2 since cutover are lost**, so communicate it. After the window, fix forward only |

V1 and V2 share Git history but **not** a reversibly shared database. The rollback guarantee
is the backup, not the migrations (prompt 11.7).

## After launch: contracting the legacy path

When `max(expires_at)` of all legacy lists plus 24 h (the purge lag) has passed (roadmap task
9.6). With no V1 deployment (D32) there are no legacy lists, so 9.6 follows `v2.0.0` directly,
as `v2.1.0`:

1. Remove the `/api/v1/` routes and the legacy bearer principal.
2. Drop `owner_token_hash` in a later release (contract step). Drop the backup and restore UI
   and the edit-link route. Keep `/l/{code}/manage` as a redirect to `/l/{code}`.
3. Tighten CHECK L2 to `owner_id IS NOT NULL` (and drop L3).
