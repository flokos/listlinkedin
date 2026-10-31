# 22: Release rehearsal

Task 9.5. The V1 → V2 release ([06](06-MIGRATION-PLAN.md#deployment-strategy-release-day)) was
rehearsed on 2026-10-31 with [deploy/rehearse-release.sh](../../deploy/rehearse-release.sh).
The script follows the [runbook](06-MIGRATION-PLAN.md#runbook) on one machine, with the
runbook's own commands, in one isolated compose project, and checks the result:

- V1 runs and holds the data;
- V2's nginx takes over with the maintenance page;
- V1 stops and is dumped;
- V2 migrates and starts, and the page ends;
- the rollback puts the dump and V1's images back in place. This page records what it measured and found, and answers Q9 as far as a
rehearsal can.

## What was rehearsed

| | |
|---|---|
| V1 | `main` at `fb5f901` (PR #7), its production stack, built from a git worktree |
| V2 | `v2` at `f058e1f` (PR #44) plus this task's changes, its production stack |
| Machine | 4 cores, 7 GB RAM, rootless Docker, SSD (the developer laptop of task 9.2) |
| Data | No production dump was available here. The kept `listlinkedin-demo` volume already held early V2 migrations (`sharing.0002`, `accounts.0001`), so it isn't V1 data. V1 itself created the data instead: one list with 3 links through V1's API, with a real edit-link token, then 20,000 lists of 10 links each in SQL, in V1's schema. 1% of them were already expired, as in a live V1 database. Total: 20,001 lists, 200,003 links, 200,003 short URLs, 111 MB |

[06](06-MIGRATION-PLAN.md#schema-and-data-migrations-by-phase) assumes production holds at
most tens of thousands of lists. V1 lists live 30 days, so 20,000 is a generous stand-in.
**Run the script again on a copy of the real production dump before release day**:
`bash deploy/rehearse-release.sh v1-prod.dump`. Only do that on a machine allowed to hold
production data.

## Timings

Four runs, within about 15% of each other. Below are the figures from the last run, which
followed the runbook in place.

| Step | Duration |
|---|---|
| Maintenance page on: V2's nginx replaces V1's | under 2 s |
| Pre-cutover `pg_dump -Fc`, checked with `pg_restore --list` | 2.8 s (24 MB) |
| **`migrate`, V1 schema → V2** | **29.5 s** |
| — `sharing.0004_backfill_link_positions` | 8.9 s |
| — `sharing.0002_list_ownership` (slug backfill, CHECKs) | 7.6 s |
| — `versioning.0003_baseline_revisions` (20,001 snapshots) | 5.0 s |
| — `sharing.0005_link_constraints` | 1.0 s |
| — everything else | under 1 s each |
| V2 start, until every service is healthy | 19.9 s |
| **Maintenance window, page on to page off** | **54.5 s** |
| `backfill_metadata --dry-run` | 6.9 s: 198,003 links to fetch |
| `cleanup_expired` (the 200 expired lists) | 3.0 s |
| **Rollback**: page on, V2 stopped, dump restored, V1's images started | **20.0 s** |

At this size, the site is down for about a minute. Building V2's images happens before the
page goes up, while V1 still serves. Plan a 30-minute window. It leaves room for the browser
checklist, and for a rollback, which takes 20 s plus the checks.

Across runs, `sharing.0004` took 8.9–13.1 s, around the 10 s mark in 06. That mark is for
steps that lock tables while the site serves traffic. The migration runs during the
maintenance window, when nothing else uses the database, so it stays as it is. A production
dump much larger than this one should be timed first, with the script above.

## Checks (all 26 passed)

During the cutover:

- the maintenance page answers 503 while V1 still runs;
- it stays up after V2 has started;
- V2 answers once the page is off.

After the migration:

- **Nothing was lost:** every list's id, code and expiry, every link's id and URL, and every
  short URL's code and target are identical before and after. The script compares counts
  and digests.
- **Legacy lists:**
  - every list is `unlisted` and has no owner;
  - every list keeps its token hash and its expiry;
  - each has exactly one `migrated` revision at head 1, holding all of its links.
- **Link order:** link positions run `0..n-1` per list, newest first, as V1 showed them.
- **Through nginx:**
  - a short URL redirects (302) to its destination;
  - an expired list's short URL answers 410;
  - `/l/{code}` loads;
  - the v2 API reads the list anonymously (`unlisted`), and the V1 API reads it too.
- **The edit link:** a real V1 edit-link token still edits its list through `/api/v1/`, and
  the edit writes revision 2.
- **Claiming:**
  - a verified V2 account signs in through allauth;
  - it claims the list with the token (200);
  - the token then stops working (403).
- **The worker:** both replicas are healthy.

**Rollback:**

- V1 runs again on the pre-cutover dump and serves the list and its short URLs;
- every list is back as it was, with the same ids, codes and expiry;
- V2's writes (the edit, the claim) are gone;
- V2's worker is removed.

## Findings

1. **nginx resolved the API's address only once, at startup.** An upgrade that recreates the
   api container can give it a new address, and nginx would keep sending requests to the old
   one until restarted. It also couldn't start at all without an api container, which the
   maintenance page needs. Fixed: Docker's resolver and a per-request lookup
   ([deploy/nginx/default.conf.template](../../deploy/nginx/default.conf.template)). The
   smoke test now recreates the api and checks that nginx still reaches it.
2. **There was no maintenance page.** It is added now. nginx serves a static 503 page with
   `Retry-After` while `deploy/maintenance/on` exists. The page stays up while V1's api is
   stopped and V2's has yet to start. The smoke test covers it
   ([deployment](../deployment.md#maintenance-mode)).
3. **V1 and V2 build the same image names** (`listlinkedin:prod`, `listlinkedin-nginx:prod`).
   Building V2 on the server overwrites V1's tags. The runbook therefore retags V1's images
   as `:v1` first, so a rollback doesn't need a rebuild.
4. **The metadata backfill must run in batches.** All 198,003 links at once would leave tasks
   waiting longer than 10 minutes. `check_worker` would then mark the workers unhealthy, and
   `deploy/autoheal.sh` would restart them and alert, again and again. The runbook runs the
   default `--limit 1000` batch whenever the queue is empty.
5. **`main` needs no reconciliation:** it is 0 commits ahead of `v2` (checked 2026-10-31).
   Step 1 of [16](16-GIT-WORKFLOW.md#releasing-v2) is a no-op.

## Not rehearsed here

- The full e2e suite against the migrated staging data. CI runs it against a fresh V2 stack
  on every PR. On migrated data, the checks above cover legacy lists and claiming.
- A production-sized dump (see above).
- The manual accessibility and device pass ([qa-checklist](../qa-checklist.md)), which is
  the owner's.
