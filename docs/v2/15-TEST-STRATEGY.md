# 15: Test strategy

V2 reuses V1's tooling (pytest + pytest-django on real PostgreSQL, Vitest + @vue/test-utils,
Playwright in five browser projects, axe) and its habits: real concurrency tests, mutation
checks of the smoke test, no mocked database. Only two dev tools are added:

- **Hypothesis**, for property-based tests of the pure merge engine. Synchronization is the
  highest-risk subsystem, and properties like convergence and idempotence catch the cases
  hand-written examples miss. It's a pytest plugin, not a second framework.
- **pytest-cov**, to *measure* coverage. Only the domain core is gated (100 % branch coverage
  for `versioning/domain` and `sharing/policy.py`).

Test data uses plain builder functions in `conftest.py` (V1 style). There is no factory library.

## Levels

| Level | Scope | Where | Runs in |
|---|---|---|---|
| Unit (pure domain) | snapshot schema, merge engine, permission policy, URL rules | `apps/*/domain/tests`, `apps/sharing/tests/test_policy.py` | CI `checks` (no DB, milliseconds) |
| Integration | services, selectors, constraints, transactions, locks, triggers, migrations, tasks | `apps/*/tests` with `db` / `transactional_db` | CI `checks` |
| API | ViewSets, status codes, schemas, auth, CSRF, throttles, preconditions | `apps/*/tests/test_api_*.py` with `APIClient` | CI `checks` |
| Frontend unit and component | composables, components, client | `frontend/src/**/*.test.ts` | CI `checks` |
| End-to-end | journeys on the production stack over HTTPS | `e2e/tests/*.spec.ts` | CI `e2e` |
| Concurrency | real threads or processes on PostgreSQL | `transactional_db` tests (V1 `test_concurrent_*` pattern) | CI `checks` |
| Smoke | deployed stack properties | `deploy/smoke-test.sh` (+ V2 checks; since 1.4 it asserts v1 create → 410 and seeds its legacy list with `manage.py shell`) | CI `proxy` |

## Unit tests (pure domain)

- **Merge engine** (postponed with synchronization, [ADR-015](adr/ADR-015-postpone-synchronization.md)): one table-driven test per row of the
  [scenario catalogue](08-SYNCHRONIZATION-SPEC.md#scenario-catalogue) (36 rows). Each states
  BASE, PARENT, CHILD, exclusions, the expected items, defaults, allowed decisions, and the
  result after each decision.
- **Engine properties** (Hypothesis, generated snapshots of ≤30 links with random edits on
  both sides):
  1. `plan(B, P=B, C)` has no incoming items (the parent didn't change).
  2. `plan(B, P, C=B)` with ACCEPT everywhere yields `C' ≡ P` (same sources and field values;
     order as appended).
  3. KEEP_LOCAL everywhere leaves the child content unchanged.
  4. After applying any decisions, re-planning against the same P (new base = P) yields no
     items (acknowledgement, scenario 17).
  5. Determinism: the same inputs give the same plan, change ids and fingerprint, independent
     of input ordering.
  6. The engine never returns operations that touch the parent.
  7. No plan produces two live child links with the same URL or the same source.
- **Snapshot:** building, validation (positions `0..n-1`, unique URLs), canonical comparison,
  and upcasting once a v2 schema exists.
- **Policy:** the full [permission matrix](12-AUTHORIZATION.md#list-permission-matrix) as a
  parametrized table (role × visibility × action → expected), plus the group-display rules.
- **Import rule:** the domain-core packages import no Django or DRF (an AST check).

## Integration tests (Django + PostgreSQL)

Repositories and services (prompt 13.2):

- Revision persistence: every mutation writes one revision, no-ops write none, the head
  equals the live state (R4) after randomized operation sequences, the UPDATE trigger
  rejects changes, and a forced failure mid-transaction leaves neither a change nor a revision.
- Fork creation (since 5.1, `test_v2_forks.py`): atomic (a failure while writing revision 1
  leaves no list, link or short URL), copied from the head revision, permissions per
  [12](12-AUTHORIZATION.md#list-permission-matrix), `origin` never naming a source the reader
  can't view, idempotent `creation_key` (also under 8 concurrent retries), and copies made
  while the source is edited each equal one of its revisions (real PostgreSQL threads).
- Branch creation (postponed): atomic (inject a failure after copying half the links → nothing remains),
  consistent snapshot, `source_link_id` and short codes, idempotent `creation_key`.
- Merge application: each decision type against real rows, revivals keep `id` and short code,
  URL swap cycles, link cap, base advancement, exclusions upsert and pending re-inclusions,
  `SyncRecord`.
- Rollback behaviour: a DB error during apply (simulated constraint violation) rolls back the
  revision, base and exclusions.
- Short URL resolution: tombstoned → 404, revived → 302, private → 404 for anonymous and 302
  for members, expired → 410, blocked host → 410.
- Metadata: the fetcher against a local test HTTP server (redirect chains, size and time
  limits, content types) and a stubbed resolver (private IPs, mixed answers, **rebinding**:
  first answer public, second private → the connection still goes to the validated IP).
  Parser fixtures. Image pipeline (polyglot, bomb, wrong type, EXIF). Stale-result guard (URL
  changed → no write). Since 8.1 (`apps/sharing/tests/test_v2_directory.py`): tag rules and
  permissions, the list and group directories showing public resources only (unlisted,
  private, expired and leaving owners' never, for anyone), counts of only what the reader may
  see, search (words, phrases, exclusions, partial titles, relevance), tag filters, orderings,
  facets that count public resources only, the per-IP limit, and the generated column
  following edits. Since 7.3 (`apps/sharing/tests/test_v2_metadata.py`): when fetches are
  queued (create, URL change, V1 links, move, fork, restore; not for title edits or while
  off), the real worker storing without touching user fields, `updated_at` or revisions, stale
  and deleted results dropped, failures recorded and retried without erasing good values,
  status and display following the current URL, refresh permissions and its hourly limit,
  backfill, and fetched media counted by `cleanup_media`. Since 7.2 (`apps/metadata/tests/`): the local servers speak HTTP and
  HTTPS (a `trustme` test CA, so pinning is checked with real certificates), the stub resolver
  and the dial hook record every lookup and connection, and each rule of
  [13](13-SECURITY.md#ssrf-safe-fetcher) has a test, including IPv4-mapped, 6to4, Teredo and
  NAT64 addresses, a compression bomb, a trickling server and a certificate for another name.
- Migrations: a test applies V1's migration state, inserts V1-shaped rows, migrates to head,
  and asserts the data mapping in [06](06-MIGRATION-PLAN.md#data-mapping) (ids, codes, token
  hashes, positions, `unlisted`, `migrated` revisions).

## API tests

CRUD for every endpoint in [09](09-API-DESIGN.md). Authentication (session and CSRF:
missing or wrong token → 403; legacy bearer). Authorization (matrix through HTTP, 404 vs 403
vs 401). Visibility. Fork, branch and detach. Sync preview, status and apply (all error
codes). Restore with `If-Match`. Idempotency replay. Error shapes and `code`s. Pagination.
Directory filters and ordering. Throttles (V1 style). OpenAPI: v2 schema generation succeeds,
and public endpoints are unauthenticated (V1 test extended). Query counts:
`django_assert_max_num_queries` per endpoint at the targets in
[14](14-INFRASTRUCTURE.md#performance-targets-initial).

## Authorization matrix tests

Generated from the tables in [12](12-AUTHORIZATION.md): for each (principal ∈ anonymous,
signed-in, viewer, editor, owner, legacy token) × (visibility) × (action), assert the HTTP
outcome. Since task 1.5 this lives in `apps/sharing/tests/test_v2_members.py`
(`test_list_permission_matrix`), with the expected statuses written out rather than derived
from the policy. **Leak tests:** compare responses for a nonexistent and a private code (identical
status and body). Check that a public group containing private, unlisted and public lists
renders only the allowed ones for each viewer type, with counts and positions matching. Check
that directory search never returns non-public items, and that `parent_inaccessible` reveals
no parent fields.

## Synchronization acceptance tests

> **Postponed** ([ADR-015](adr/ADR-015-postpone-synchronization.md), 2026-10-29): these run once synchronization is resumed.

- All 36 catalogue scenarios at engine level (above).
- Integration or API level for the risky subset: 1, 2, 3 (short URL preserved), 8, 9, 10, 11
  (revival with the same short code), 14 (adopt), 15–17, 18, 19, 22, 23, 24, 28, 31, 32, 33.
- The prompt's E2E flow (below) plus "Review again" after a stale preview.

## Concurrency tests (prompt 13.6)

Real threads against PostgreSQL (`transactional_db`, V1's barrier pattern):

| Test | Expectation |
|---|---|
| Simultaneous edits to two links of one list | both applied, revisions n+1 and n+2, no lost update |
| Concurrent moves of different links | serialized; final order equals some serial order; positions `0..n-1` |
| Duplicate short codes | V1 collision simulation, extended to group codes |
| Two simultaneous applies with the same key | one apply, one replay |
| Two simultaneous applies with different keys | one 200, one 409 `stale_preview` |
| Stale revisions | restore and apply with an old `If-Match` → 412 |
| Metadata race | a manual title edit while the fetch completes → the title is kept, metadata stored, no revision |
| Duplicate requests | create list, fork and branch with the same `Idempotency-Key` → one resource |
| Parent deleted during sync | apply either completes against revision P or returns 409. Never a partial state |
| Concurrent permission change | revoke an editor during their write → the write is rejected (403) or committed before the revoke. Never after |
| Link cap race | V1 test kept |

## End-to-end scenarios

Playwright, production stack, Mailpit for email. Chromium runs everything. Firefox, WebKit and
the phone projects run the journeys marked ★.

1. ★ The prompt's flow: create account → create list → add links (tiles show fetched titles,
   using a fixture site served inside the e2e network) → create group → add list → make a
   copy (second user; since 5.2 in `copy.spec.ts`, with the sign-in detour). The fetched
   titles: since 7.3 in `metadata.spec.ts`, against `e2e/fixture-site` (title, site name and
   icon without a reload, Details, refresh limit, edit suggestion, an unfetchable page).
   *Postponed with synchronization:* modify the parent → see "updates" →
   review, resolve a conflict → apply → verify the child.
2. ★ Legacy owner: seed a legacy list (through `POST /api/v1/lists/`, which the e2e stack
   keeps open with `LEGACY_LIST_CREATION=on`; production answers 410) → open the edit link → sign in → add to account → token gone
   from storage → V1 short URL still redirects.
3. ★ Group workspace on a phone: open the drawer, switch lists, focus lands on the `<h1>`, Escape
   closes (`e2e/tests/groups.spec.ts`, since task 4.3, which also covers building a group,
   reordering without dragging, the tablet rail and what visitors see).
4. Reorder: drag on desktop; ⋮ Move up on a phone; keyboard-only Move; the order persists after
   reload; the live region announces (`e2e/tests/reorder.spec.ts`, since task 2.5, with a
   long-press touch drag on mobile-chrome and Move to another list).
5. Visibility: a private list → the anonymous view is "not found". Unlisted → readable by link,
   absent from Explore. Public → found in Explore (`e2e/tests/explore.spec.ts`, since task 8.2:
   the owner tags a public list in the UI, a signed-out visitor finds it by a partial word and
   by its tag, the address keeps the search across a reload, words that match only an
   unlisted list find nothing, and public groups have their own tab; axe on `/explore` and the
   Tags dialog in `a11y.spec.ts`).
   List settings (`e2e/tests/list-settings.spec.ts`, since task 8.3): the owner changes the
   description, image and expiry and the list shows them; a description changed meanwhile is
   refused and the current one shown; a visitor can't change anything, and an edit link gets
   only name, description and delete. Axe on the settings page in `a11y.spec.ts`.
6. History: edit, restore version 2 → a new version is created and the restored links come
   back with the same short URLs (`e2e/tests/history.spec.ts`, since task 3.4; axe on the
   history page and the restore dialog in `a11y.spec.ts`).
7. Access: a viewer can't see edit controls, and a forced API write returns 403.
8. Auth flows: sign up, verify, sign out, reset password (`e2e/tests/auth.spec.ts`, since task
   1.2). These run in all five projects, because cookies, CSRF and `Origin` handling are where
   engines differ. Emails are read from Mailpit's API.
9. States (mocked like V1's `states.spec.ts`): 412 on edit (since 3.4: refused, reloaded, the
   input kept for retrying), offline. *Postponed:* stale preview
   409, merge failure 500.
10. a11y: axe on every new page (V1 `a11y.spec.ts` extended). Keyboard spec extended to tiles,
    ⋮ menus and decisions.

## V1 regression checklist

V1 behaviour that must survive (prompt 13.7). Every V1 test keeps running. Tests whose
behaviour changes on purpose are **replaced** in the PR that changes the behaviour, with a
link to the decision.

| V1 behaviour / test file | V2 status |
|---|---|
| Codes are 16 chars, 96 bits, collision retry, DB uniqueness (`test_shortener.py`) | **Keep** unchanged |
| `/r/` 302 to the current destination; `no-store`, `no-referrer`; 404 unknown; 410 expired, inactive or blocked; trailing slash tolerated | **Keep**. Add: private → 404, tombstoned → 404, revived → 302 |
| The short code survives destination edits (`test_links.py`) | **Keep** (K1) |
| Deleting a link removes its row and short code (`test_links.py::test_owner_can_remove_link`, `test_shortener.py::test_deleted_link_stops_redirecting`) | **Replaced** in task 2.1 ([ADR-013](adr/ADR-013-soft-delete-links-only.md)): the link becomes a tombstone, disappears from both APIs, and its short URL still answers 404; the row and short code are kept for history and restore |
| Anonymous reads never expose secrets; token only on create or rotate (`test_lists.py`, `test_security.py`) | **Keep** for v1 and v2 representations |
| Owner token checks, rotation, the token rotated mid-request → 403, a token from another list rejected | **Keep** for legacy lists. Claimed lists → 403 (new test) |
| Mass assignment blocked; immutable fields | **Keep** (v1 + v2 serializers) |
| Normalization, IDNA, denylist, own-host block, byte limit (`test_domain.py`, `test_security.py`) | **Keep** |
| Throttles exact under concurrency; spoofed `X-Forwarded-For` ignored; the cache isn't culled | **Keep**. Add the new scopes |
| Expiry: 410 at the exact instant, edits don't extend, cleanup purges and is idempotent, overlapping runs skipped (`test_expiration.py`) | **Keep** for lists with `expires_at`. Add: permanent lists never expire; branches of purged parents get `parent_deleted_at` |
| Link cap 100 including the concurrent race | **Keep** |
| `/l/{code}` on Django → 302 to the API | **Keep** |
| `/healthz` behaviour; deploy checks pass | **Keep**. Deploy checks without the W003 silence |
| OpenAPI marks only owner operations as authenticated | **Adapt**: v1 unchanged; a new v2 assertion with the session and bearer schemes |
| `POST /api/v1/lists/` creates a list anonymously | **Replaced** (ADR-011): v1 create → 410, plus v2 create tests for signed-in users |
| `GET /api/v1/…/links/` newest first, paginated | **Keep** for the v1 endpoint (compatibility). v2 orders by `position` |
| Full workflow (`tests/integration/test_workflow.py`) | **Keep** on a legacy list (seeded through the ORM). Add a V2 workflow test |
| Frontend: `api.test.ts`, `useOwnedLists`, `useEditLink`, backup, url and time utils, `LinkForm` | **Keep**. `api.test.ts` adapts to the split client. Backup and edit-link tests stay until the legacy sunset |
| E2E: `create.spec` (anonymous create) | **Replaced** by signed-in create (task 1.4), plus `claim.spec` for the legacy journey (scenario 2) |
| E2E: `ownership`, `share`, `links`, `navigation`, `keyboard`, `states`, `a11y`, `limits`, `content`, `lists-page`, `smoke` | **Keep** or adapt selectors to tiles and the new nav. `ownership` runs on seeded legacy lists. Since 1.4, `keyboard` and the creation case in `states` sign in first, and `states` mocks `/api/v2/` |
| Manual QA checklist | **Extend** ([11](11-UI-UX-MIGRATION.md#accessibility-wcag-22-aa)) |

## Acceptance test matrix (summary)

| Requirement area | Unit | Integration | API | Frontend | E2E | Concurrency |
|---|---|---|---|---|---|---|
| Link identity (K1–K6) | ✓ | ✓ | ✓ | | 6 | ✓ |
| List invariants (L1–L6) | | ✓ | ✓ | | 5 | ✓ |
| Revisions (R1–R5) | ✓ | ✓ | ✓ | ✓ | 6 | ✓ |
| Branch identity and creation (B1–B7) | ✓ | ✓ | ✓ | | 1 | ✓ |
| Diff, conflicts, decisions, exclusions | ✓ (36) | ✓ (subset) | ✓ | ✓ | 1, 9 | ✓ |
| Permissions and visibility | ✓ (matrix) | ✓ | ✓ (matrix, leaks) | ✓ | 5, 7 | ✓ |
| Groups | ✓ | ✓ | ✓ | ✓ | 1, 3 | |
| Auth and claim | | ✓ | ✓ | ✓ | 2, 8 | ✓ |
| Short URLs | | ✓ | ✓ | | 2, 6 | ✓ |
| Metadata and SSRF | ✓ | ✓ | ✓ | ✓ | 1 | ✓ |
| Media | ✓ | ✓ | ✓ | | 1 | |
| Directory and search | | ✓ | ✓ | ✓ | 5 | |
| Responsive and a11y | | | | ✓ | 3, 4, 10 | |
| V1 regression | | ✓ | ✓ | ✓ | 2 + kept specs | ✓ |
