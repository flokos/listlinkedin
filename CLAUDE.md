# CLAUDE.md

Working rules for Claude Code sessions (and people) on the **`v2` branch** of listlinkedin.
Version 1 is documented in [README.md](README.md) and [docs/](docs/). Version 2 is planned in
[docs/v2/](docs/v2/README.md).

## Branches: V1 is `main`, V2 is `v2`

- `main` is Version 1. `v2` is the long-lived integration branch for Version 2. The default
  branch stays `main`.
- Start every V2 task from the current `v2`:
  `git fetch origin && git switch -c feature/<area>-<topic> origin/v2`
  (`feature/`, `fix/`, `docs/`, `chore/`). One roadmap task per branch and PR.
- **Every V2 pull request targets `v2`:** `gh pr create --base v2`. To make that the default
  for a branch: `git config branch.<branch>.gh-merge-base v2`. Never open a V2 PR against
  `main`. CI's `checks` job fails one if it happens.
- Never commit, merge or push to `main` from V2 work. Never force-push, rebase, reset or delete
  `main` or `v2`. Both are protected by rulesets: PR plus the `checks` job required.
- V1 bug fixes: `bugfix/v1-<topic>` from `main`, PR into `main`. Then port with
  `git cherry-pick -x <sha>` on a branch from `v2`, PR into `v2`. Never merge `main` into `v2`
  without reviewing each change ([16-GIT-WORKFLOW.md](docs/v2/16-GIT-WORKFLOW.md)).
- `v2` reaches `main` only through the planned release PR (roadmap phase 9).

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
| `sharing` | Lists (`SharedList`) and Links (`SharedLink`), list memberships, legacy owner tokens |
| `shortener` | Short codes, `ShortRedirect`, `/r/{code}` resolution (visibility checked through `sharing` selectors) |
| `accounts` | Custom `User` (email login, UUID key), session authentication, `/api/v2/session/` and `/api/v2/me/`. Sign-up, sign-in and passwords via django-allauth's headless API under `/_allauth/` |
| `common` (not a Django app) | `errors.py`: framework-free `DomainError` classes, mapped to HTTP by `config/exceptions.py` |
| `groups` (planned) | `Group`, `GroupList`, `GroupMembership` |
| `versioning` (planned) | `ListRevision`, snapshots and diffs in `versioning/domain/`, which has **no Django imports**. `ListBranch`, `BranchExclusion`, `SyncRecord` and the merge engine are **postponed** ([ADR-015](docs/v2/adr/ADR-015-postpone-synchronization.md)) |
| `metadata` | The image pipeline (`images.py`: re-encoding, storage) and `cleanup_media`, since 2.3. Planned: safe URL fetching, metadata parsing (worker tasks) |

- DRF ViewSets handle HTTP only. Services own transactions and row locks. Selectors own reads.
  One app never writes another app's models directly; it calls that app's services.
- Every permission decision goes through the policy module ([12-AUTHORIZATION.md](docs/v2/12-AUTHORIZATION.md)).
  List querysets are filtered by visibility in SQL, not after loading.
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
7. A legacy owner token grants V1-equivalent rights on its own list only.

## Commands (Docker only: no virtualenv, no host Python or Node)

```bash
docker compose up --build -d                                   # dev stack (mail it sends: http://localhost:8025)
docker compose run --rm api pytest                             # backend tests (PostgreSQL)
docker compose run --rm --no-deps api sh -c "ruff check . && ruff format --check ."
docker compose run --rm api python manage.py makemigrations --check --dry-run
docker compose exec frontend sh -c "npm run lint && npm run type-check && npm run test && npm run check:contrast"
bash e2e/run.sh                                                # Playwright, production stack
```

## Definition of done for every V2 PR

- The PR targets `v2`, and CI (`checks`, `proxy`, `e2e`) is green.
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
