# CLAUDE.md

Working rules for Claude Code sessions (and people) on listlinkedin. **`main` is Version 2**
(released as `v2.0.0` on 2026-10-31). Version 2 is described in the root [README.md](README.md),
operated per [docs/deployment.md](docs/deployment.md), and specified in
[docs/v2/](docs/v2/README.md). Version 1 is documented in [docs/v1/](docs/v1/README.md) and
kept on `release/v1`.

## Branches: V2 is `main`, V1 is `release/v1`

- Start every task from the current `main`:
  `git fetch origin && git switch -c feature/<area>-<topic> origin/main`
  (`feature/`, `fix/`, `docs/`, `chore/`). One roadmap task per branch and PR, into `main`.
- Never commit or push to `main` directly. Never force-push, rebase, reset or delete `main` or
  `release/v1`. `main` is protected by a ruleset: PR plus the `checks` job required.
- `release/v1` (tag `v1.0.0`) is Version 1, kept so it can be rebuilt. V1 fixes, if ever
  needed: a branch from `release/v1`, PR into `release/v1`. Port to `main` only what still
  applies, with `git cherry-pick -x <sha>` ([16-GIT-WORKFLOW.md](docs/v2/16-GIT-WORKFLOW.md)).
- `v2` was the integration branch until the release (PR #46). It is frozen: don't branch from
  it or merge into it.
- Releases are tags on `main` (`v2.1.0`, …) with a GitHub Release. V1 was never deployed
  (D32), so there is no production to cut over.
- The browser extension is released apart from the site: a tag `extension-v<version>` on
  `main` runs `extension-release.yml` ([docs/extension.md](docs/extension.md),
  [ADR-021](docs/v2/adr/ADR-021-extension-distribution.md)). Its release is never marked
  "latest": the server deploys the latest release. Installed Firefox add-ons then update
  from `frontend/public/extension-updates.json` when the site is released
  ([ADR-023](docs/v2/adr/ADR-023-extension-self-updates.md)): the add-on stays unlisted, as
  Mozilla refuses `update_url` in listed ones.

## Read before changing anything architectural

1. [docs/v2/README.md](docs/v2/README.md): index, glossary and the decision summary.
2. The spec for the area you touch: domain [04](docs/v2/04-DOMAIN-MODEL.md), database
   [05](docs/v2/05-DATABASE-DESIGN.md), revisions [07](docs/v2/07-REVISION-SPEC.md),
   synchronization [08](docs/v2/08-SYNCHRONIZATION-SPEC.md), API [09](docs/v2/09-API-DESIGN.md),
   authorization [12](docs/v2/12-AUTHORIZATION.md), security [13](docs/v2/13-SECURITY.md).
3. The ADRs in [docs/v2/adr/](docs/v2/adr/README.md). They are binding. To change a decision,
   add a superseding ADR and update the affected docs **in the same PR**.
4. The next task in [17-IMPLEMENTATION-ROADMAP.md](docs/v2/17-IMPLEMENTATION-ROADMAP.md).
   Tick it off in the PR that completes it.

If the code and the docs disagree, stop and reconcile them. Never let them silently diverge.

## Domain boundaries (backend/apps/)

| App | Owns |
|---|---|
| `sharing` | Lists (`SharedList`) and Links (`SharedLink`), list memberships. Moderation since 9.0: `services/moderation.py` (reports, the operator email, operator actions; the commands live in each app) |
| `shortener` | Short codes, `ShortRedirect`, `/r/{code}` resolution (visibility checked through `sharing` selectors) |
| `accounts` | Custom `User` (email login, UUID key), session authentication, `/api/v2/session/` and `/api/v2/me/`. Sign-up, sign-in and passwords via django-allauth's headless API under `/_allauth/`. Suspended accounts (`suspended_at`, since 9.0) are refused by `backends.py` and `adapter.py`; `is_active` means erased. Connected browsers since 11.1 (`browsers.py`, `ConnectedBrowser`, [ADR-020](docs/v2/adr/ADR-020-connected-browsers.md)): the browser extension's long-lived session tokens, approved from this site's cookie session only |
| `common` (not a Django app) | `errors.py`: framework-free `DomainError` classes, mapped to HTTP by `config/exceptions.py` |
| `groups` | `Group`, `GroupList`, `GroupMembership`, since 4.1. Group rules are in `sharing/policy.py`; the display rule in SQL is `groups/selectors.shown_lists_q` |
| `versioning` | `ListRevision`, `record_revision`, snapshots and diffs in `versioning/domain/`, which has **no Django imports** (an AST test enforces it). `ListBranch`, `BranchExclusion`, `SyncRecord` and the merge engine are **postponed** ([ADR-015](docs/v2/adr/ADR-015-postpone-synchronization.md)) |
| `metadata` | The image pipeline (`images.py`: re-encoding, storage) and `cleanup_media`, since 2.3. The task queue since 7.1: `tasks.py` is the only place that queues work (`enqueue_on_commit`, `retry_or_give_up`), plus `check_worker` and `recover_stuck_tasks`. Since 7.2: `fetcher.py` (the only code that fetches user URLs), `parser.py`, `extraction.py`; since 7.3 the task `fetch_link_metadata`, which stores through `sharing/services/metadata.py` |

- DRF ViewSets handle HTTP only. Services own transactions and row locks. Selectors own reads.
  One app never writes another app's models directly; it calls that app's services.
- Every permission decision goes through the policy module ([12-AUTHORIZATION.md](docs/v2/12-AUTHORIZATION.md)).
  List querysets are filtered by visibility in SQL, not after loading.
- `extension/` (since 11.2) is the browser extension: a client of `/api/v2/`, not a domain app.
  It sends `X-Session-Token` with `credentials: 'omit'`, asks for no site but the one it was
  built for, and shows what `permissions` allow instead of deciding itself. Copying a link
  never changes who can open a list: only the user's choice in the popup does (invariant 2),
  and menus and shortcuts act only on a list the user saved to before. Its message
  protocol with the Connect page has two halves that change together:
  `extension/src/lib/bridge.ts` and `frontend/src/utils/extensionBridge.ts`.
- `List` and `Link` stay the central concepts. Don't add a `WebApp` entity, and don't rename
  `SharedList`/`SharedLink` or their tables.

## V2 invariants (never violate)

1. A List keeps its `id` and `public_code` forever. A Link keeps its `id` and short code when
   its URL changes.
2. A short URL never bypasses the visibility of the list it belongs to.
3. Every content change writes exactly one immutable revision in the same transaction. A no-op
   writes none. A restore writes a new revision. History is never rewritten.
4. Synchronization never modifies the parent and never applies a parent change without an
   explicit decision. Merges are previewed, fingerprinted, idempotent and atomic. (Applies
   once synchronization is resumed; it is postponed by ADR-015.)
5. A Group never grants access to its Lists. Lists the viewer may not see are omitted entirely.
6. Fetched metadata never overwrites user-entered fields. User URLs are fetched only through
   the SSRF-safe fetcher.
7. Every list has an owner account. Nothing but an account's role grants rights on a list (the
   V1 owner tokens were retired in v2.1.0, task 9.6).

## Commands (Docker only: no virtualenv, no host Python or Node)

```bash
docker compose up --build -d                                   # dev stack (mail it sends: http://localhost:8025)
docker compose run --rm api pytest                             # backend tests (PostgreSQL)
docker compose run --rm --no-deps api sh -c "ruff check . && ruff format --check ."
docker compose run --rm api python manage.py makemigrations --check --dry-run
docker compose exec frontend sh -c "npm run lint && npm run type-check && npm run test && npm run check:contrast"
bash e2e/run.sh                                                # Playwright, production stack
docker build --target dev -t listlinkedin-extension:dev extension   # the browser extension:
docker run --rm listlinkedin-extension:dev sh -c "npm run lint && npm run format:check && npm run type-check && npm run test"
rm -rf extension/dist && docker build --target export --output extension/dist extension   # dist/chrome, dist/firefox, a zip of each
```

## Definition of done for every V2 PR

- The PR targets `main`, and CI (`checks`, `proxy`, `e2e`) is green.
- New behaviour has tests at the right level ([15-TEST-STRATEGY.md](docs/v2/15-TEST-STRATEGY.md)).
  Concurrency-sensitive code has a real PostgreSQL concurrency test.
- Migrations are reversible or documented as one-way in [06-MIGRATION-PLAN.md](docs/v2/06-MIGRATION-PLAN.md).
- The OpenAPI schema, docs and ADRs match the code. The roadmap task is ticked off.
- V1 tests are never deleted because they fail. If the behaviour changes on purpose, replace
  them with acceptance tests and record why.

## Don't

- Don't add Redis, Celery, RabbitMQ, Kafka, Elasticsearch, extra databases or services without
  an accepted ADR ([14-INFRASTRUCTURE.md](docs/v2/14-INFRASTRUCTURE.md)).
- Don't fetch user-supplied URLs outside `metadata`'s fetcher. Never put tokens in URLs or logs.
- Don't build synchronization (synced copies, sync preview or apply, the merge engine, branch
  tables) while [ADR-015](docs/v2/adr/ADR-015-postpone-synchronization.md) stands. Forks
  ("Make a copy") are in scope. Keep the existing design docs and `allow_branch` as they are.
- Don't implement multi-parent merges, parent-order sync or re-parenting of branches. These
  are deferred on purpose ([08](docs/v2/08-SYNCHRONIZATION-SPEC.md)).
