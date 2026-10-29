# 19: Research references

Research was done on **2026-10-28** during the planning run, with web search, page fetches,
the PyPI and npm registry APIs, the GitHub API, and local tools (the V1 Docker image, `gh`).
"How verified" says exactly what was seen, and nothing is claimed beyond it. Where only
search-result snippets or secondary sources were available, the reference says so. Facts used
from prior knowledge but **not** verified in this run are listed separately at the end.

| Id | Source | Date | How verified | Used for |
|---|---|---|---|---|
| R1 | Django docs, "Customizing authentication": *Using a custom user model when starting a project*, *Changing to a custom user model mid-project*, *Referencing the User model*. https://docs.djangoproject.com/en/5.2/topics/auth/customizing/ | 5.2 docs (live) | **Fetched.** Quotes: set `AUTH_USER_MODEL` "before creating any migrations or running `migrate` for the first time"; mid-project change "can't be done automatically"; the model "must be created in the first migration of its app" | [ADR-007](adr/ADR-007-authentication-and-ownership-migration.md), [06](06-MIGRATION-PLAN.md) |
| R2 | Django 6.0 release notes. https://docs.djangoproject.com/en/6.0/releases/6.0/ | 2025-12-03 | **Fetched.** Tasks framework (built-in backends for development and testing only, execution by external workers); CSP middleware and `SECURE_CSP`; `DEFAULT_AUTO_FIELD` now `BigAutoField`; Python ≥3.12 | [ADR-008](adr/ADR-008-background-metadata-extraction.md), [ADR-014](adr/ADR-014-django-version.md) |
| R3 | Django download page, supported versions. https://www.djangoproject.com/download/ | live | **Fetched.** Latest 6.1.2; 5.2 LTS 5.2.18, extended support until April 2028; 6.0.9 until April 2027; 6.1 until December 2027; 6.2 LTS planned for April 2027, supported until April 2030 | [ADR-014](adr/ADR-014-django-version.md) |
| R4 | django-tasks on PyPI. https://pypi.org/project/django-tasks/ | 0.12.0, 2026-02-06 | **Fetched** + PyPI JSON: classifiers Django 4.2–6.0, "Production/Stable"; the database and RQ backends split out at 0.12.0 | [14](14-INFRASTRUCTURE.md#background-worker) |
| R5 | django-tasks-db. https://github.com/RealOrangeOne/django-tasks-db + PyPI JSON | 0.13.0, 2026-08-28 | **README fetched** (backend `django_tasks_db.DatabaseBackend`, `db_worker`, `prune_db_task_results`); PyPI JSON (Beta, Django 5.2/6.0); **GitHub code search**: `skip_locked` appears in `django_tasks_db/models.py` | [14](14-INFRASTRUCTURE.md#background-worker), [05](05-DATABASE-DESIGN.md#concurrency-controls) |
| R6 | django-allauth headless (browser vs app clients, session cookies + CSRF). Docs mirror at mintlify.com/pennersr/django-allauth/headless/… + PyPI JSON | 65.21.0, 2026-10-26 | **Search snippets of a docs mirror** (not the official docs site) + PyPI JSON (classifiers Django 4.2–6.1, "Production/Stable"). Setting names and CSRF behaviour then **verified against the installed 65.21.0 source** in task 1.1 (below) | [ADR-007](adr/ADR-007-authentication-and-ownership-migration.md), [09](09-API-DESIGN.md#session-and-account) |
| R7 | DRF permissions guide. https://www.django-rest-framework.org/api-guide/permissions/ | live | **Fetched.** Object permissions run in `get_object()`; they are not applied to list or create views; custom views must call `check_object_permissions` | [12](12-AUTHORIZATION.md#implementation-notes) |
| R8 | DRF authentication guide, SessionAuthentication. https://www.django-rest-framework.org/api-guide/authentication/ | live | **Fetched.** CSRF is enforced only for authenticated session requests; login views must always use CSRF | [09](09-API-DESIGN.md#conventions), [13](13-SECURITY.md) |
| R9 | PostgreSQL 17, "Explicit Locking". https://www.postgresql.org/docs/17/explicit-locking.html | v17 docs | **Fetched.** Row-lock conflict table; locks held until the end of the transaction; consistent lock order as the deadlock defence; session vs transaction advisory locks | [05](05-DATABASE-DESIGN.md#concurrency-controls) |
| R10 | PostgreSQL 17, "Transaction Isolation". https://www.postgresql.org/docs/17/transaction-iso.html | v17 docs | **Fetched.** Read Committed is the default; re-evaluation semantics; Repeatable Read and Serializable need retries on SQLSTATE 40001 | [05](05-DATABASE-DESIGN.md#transaction-boundaries) |
| R11 | Django `contrib.postgres` full-text search. https://docs.djangoproject.com/en/5.2/ref/contrib/postgres/search/ | 5.2 docs | **Fetched.** `SearchVector`/`SearchQuery(search_type="websearch")`/`SearchRank`; GIN index or `SearchVectorField` + triggers; trigram functions need `pg_trgm` via `TrigramExtension` | [05](05-DATABASE-DESIGN.md#indexes-added-by-v2), [09](09-API-DESIGN.md#directory) |
| R12 | OWASP SSRF Prevention Cheat Sheet. https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html | live | **Fetched.** Case 2 (any external destination): blocklist of private, loopback, link-local and metadata ranges; validate every A/AAAA answer; connect only to validated addresses (pinning) while keeping Host/SNI; redirects disabled; http/https only; network-layer controls | [13](13-SECURITY.md#ssrf-safe-fetcher) |
| R13 | OWASP API Security Top 10 (2023), API1 Broken Object Level Authorization | 2023 | **Secondary sources only** (ISACA, Palo Alto Networks, Radware summaries via search). The official owasp.org page was not fetched | [12](12-AUTHORIZATION.md), [13](13-SECURITY.md) |
| R14 | OWASP ASVS 5.0.0 | released 2025-05-30 | **Search results** (OWASP announcement and summaries): ~350 requirements across 17 chapters, levels rebalanced | [13](13-SECURITY.md), task 9.1 |
| R15 | OWASP File Upload Cheat Sheet (content-type not trusted; image rewriting destroys injected content) | live | **Secondary sources and mirrors via search.** The official page was not fetched | [13 Media](13-SECURITY.md#media), [ADR-012](adr/ADR-012-media-and-images.md) |
| R16 | OWASP Unvalidated Redirects and Forwards Cheat Sheet. https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html | live | **Search snippets** (risk, safe pattern: server-controlled targets) | [13](13-SECURITY.md) |
| R17 | Khanna, Kunal, Pierce, *A Formal Investigation of Diff3*, FSTTCS 2007 (LNCS 4855). https://www.cis.upenn.edu/~sanjeev/papers/fsttcs07_diff3.pdf | 2007 | **Search results** (bibliographic data, main result: intuitions about diff3 fail in general). Not read in full | [ADR-004](adr/ADR-004-three-way-merge.md) (why we merge per identity, not per line) |
| R18 | Figma Engineering, *Realtime editing of ordered sequences* (fractional indexing). https://www.figma.com/blog/realtime-editing-of-ordered-sequences/ | (date not verified) | **Search results and secondary write-ups** | [ADR-005](adr/ADR-005-child-ordering-policy.md) (alternative considered) |
| R19 | IETF draft-ietf-httpapi-idempotency-key-header-07. https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/ | 2025-10-15 (draft; listed expiry 2026-04-18) | **Search results** (status and abstract). Full text not read | [08](08-SYNCHRONIZATION-SPEC.md#identifiers-fingerprints-and-idempotency), [09](09-API-DESIGN.md) |
| R20 | The Open Graph protocol. https://ogp.me/ | live | **Search snippets** (`og:title`, `og:type`, `og:image`, `og:url` required; `og:description`, `og:site_name` optional) | [13](13-SECURITY.md#ssrf-safe-fetcher) (parser) |
| R21 | W3C, Understanding WCAG 2.2 SC 2.5.7 Dragging Movements. https://www.w3.org/WAI/WCAG22/Understanding/dragging-movements | WCAG 2.2 | **Search snippets of the published page.** A single-pointer non-dragging alternative is required; keyboard support alone doesn't satisfy it | [10](10-FRONTEND-ARCHITECTURE.md#drag-and-drop), [11](11-UI-UX-MIGRATION.md#accessibility-wcag-22-aa) |
| R22 | Atlassian, Pragmatic drag and drop accessibility guidelines. https://atlassian.design/components/pragmatic-drag-and-drop/accessibility-guidelines/ | live | **Search snippets** (accessible controls aren't automatic; action-menu alternative; announce results) | [10](10-FRONTEND-ARCHITECTURE.md#drag-and-drop) |
| R23 | npm registry API (`registry.npmjs.org`) | accessed 2026-10-28 | **Registry data**: vue-draggable-plus 0.6.1 (2026-01-11), @formkit/drag-and-drop 0.6.1 (2026-06-15), @atlaskit/pragmatic-drag-and-drop 4.0.0 (2026-09-24), sortablejs 1.15.7 (2026-02-11), pinia 4.1.0 (2026-10-14), openapi-typescript 7.13.0 (2026-02-11) | [10](10-FRONTEND-ARCHITECTURE.md) |
| R24 | PyPI JSON API | accessed 2026-10-28 | **Registry data**: Pillow 13.0.0 (2026-10-16), httpx 0.28.1 (2024-12-06, "Beta"), djangorestframework 3.18.3 (2026-10-06, Django 5.2–6.1), drf-spectacular 0.30.0 (2026-07-06) | [13](13-SECURITY.md#media), [14](14-INFRASTRUCTURE.md) |
| R25 | GitHub Docs, "Events that trigger workflows" (`pull_request`). https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows | live | **Fetched.** `GITHUB_SHA` is the PR merge commit (`refs/pull/N/merge`); no runs while the PR has a merge conflict; `branches` filters match the base. That the workflow *file* comes from the merge commit is implied by the `pull_request_target` contrast, not stated outright | [16](16-GIT-WORKFLOW.md#preventing-prs-into-main) |
| R26 | GitHub REST API, repository rules. https://docs.github.com/en/rest/repos/rules | API 2022-11-28 | **Fetched.** Create-ruleset body; `bypass_mode` `always` / `pull_request` / `exempt`; rule parameter shapes; `GET /rules/branches/{branch}` | [16 Rulesets](16-GIT-WORKFLOW.md#rulesets) |
| R27 | GitHub Docs, "Available rules for rulesets" / "About rulesets" | live | **Search snippet** says rulesets are available for public repositories on GitHub Free. A fetched "About rulesets" page mentioned Team/Enterprise generically. **Resolved empirically** on 2026-10-28: both rulesets were created and are enforced on this public repository ([16](16-GIT-WORKFLOW.md#enforcement-status)) | [16](16-GIT-WORKFLOW.md) |
| R28 | GitHub Docs, "Creating a pull request template" (GHE 2.7, 2.9, 3.0 versions) | older doc versions | **Search snippets.** Templates must be on the default branch to be used | [16](16-GIT-WORKFLOW.md#preventing-prs-into-main) |
| R29 | GitHub CLI 2.102.0 (2026-09-30), `gh pr create --help` | local | **Local tool output.** Without `--base`, gh uses the `branch.<name>.gh-merge-base` git config, else the default branch | [16](16-GIT-WORKFLOW.md#daily-v2-work), [CLAUDE.md](../../CLAUDE.md) |
| R30 | Python SSRF-protection libraries: drawbridge, ssrfguard, httpx-secure (last push 2025-08-16), Champion (Advocate fork), ressrf (created 2026-05-09) | various | **Search results only.** Maintenance not verified, so a dependency is not adopted | [13](13-SECURITY.md#ssrf-safe-fetcher) |
| R31 | GitHub Actions run of CI on `fb5f901` (push to `main`) | 2026-10-28 09:19 UTC | **`gh run list`**: conclusion `success` | [01](01-V1-AUDIT.md#summary) |

Local verification (not web sources):

- V1 test baseline (2026-10-28): ruff, `makemigrations --check`, pytest (129 passed),
  frontend lint, format, type-check, Vitest and contrast, all run in an isolated compose
  project ([01](01-V1-AUDIT.md#summary)).
- Django 5.2.18 (V1 image): `UniqueConstraint(condition=…, deferrable=…)` raises "UniqueConstraint
  with conditions cannot be deferred"; `Field.db_default` exists ([05](05-DATABASE-DESIGN.md)).
- Git and GitHub state: `git` and `gh api` (repository public, ADMIN permission, no protection,
  no rulesets).
- GitHub API after task 0.3 (2026-10-28): RepositoryRole id 5 is `admin` (GraphQL
  `bypassActors.repositoryRoleName`), `GET /apps/github-actions` returns id 15368, and the
  rules enforced per branch match the plan ([16](16-GIT-WORKFLOW.md#enforcement-status)).
- django-allauth 65.21.0 source, read in the V2 image during task 1.1 (2026-10-28):
  `ACCOUNT_LOGIN_METHODS`, `ACCOUNT_SIGNUP_FIELDS`, `ACCOUNT_USER_MODEL_USERNAME_FIELD`,
  `ACCOUNT_EMAIL_VERIFICATION`, `ACCOUNT_PREVENT_ENUMERATION`, `HEADLESS_ONLY`,
  `HEADLESS_CLIENTS`, `HEADLESS_FRONTEND_URLS` (keys `account_confirm_email`,
  `account_reset_password`, `account_reset_password_from_key`, `account_signup`) and
  `ALLAUTH_TRUSTED_PROXY_COUNT` (rightmost-hop `X-Forwarded-For`) exist. Browser-client views
  are CSRF-protected and set the CSRF cookie themselves; app-client views are CSRF-exempt,
  which is why only the browser client is enabled.
- GitHub's Mermaid renderer (2026-10-28, checked in a browser on the rendered pages): all 13
  diagrams in `docs/v2` render, after fixing an edge label with parentheses (03) and
  semicolons in sequence messages (07).
- Pillow 13.0.0 in the V2 image (task 2.3, 2026-10-29, verified by the tests in
  `apps/metadata/tests/test_images.py`): `Image.open` checks `MAX_IMAGE_PIXELS` from the header,
  before decoding. It warns (`DecompressionBombWarning`) above the limit and raises
  `DecompressionBombError` above twice it, so the pipeline turns the warning into an error.
  The manylinux wheel encodes WebP (`features.check("webp")`). `ImageOps.contain` enlarges small
  images, so the pipeline uses `thumbnail` (shrink only).

## Not verified in this run (prior knowledge, verify during implementation)

| Claim | Where used | Verify in |
|---|---|---|
| urllib3 2.x: `server_hostname` / `assert_hostname` on connection pools opened by IP | [13 SSRF](13-SECURITY.md#ssrf-safe-fetcher) | task 7.2 |
| PostgreSQL checks non-deferrable unique indexes per row (so URL swaps need parking) | [08 Apply](08-SYNCHRONIZATION-SPEC.md#apply-algorithm) | task 6.2 test (scenario 23) |
| Vuetify 4 navigation drawer props `rail`, `permanent`, `temporary` (the docs page could not be fetched) | [11 Groups](11-UI-UX-MIGRATION.md#groups-workspace) | task 4.3 |
| Django `GeneratedField` can store a `simple`-config `SearchVector` | [05](05-DATABASE-DESIGN.md#indexes-added-by-v2) | task 8.1 |

## Research areas covered (prompt Part 16)

Architecture (R2, R7, prior art in V1 docs) · versioning and synchronization (R17, R18, R19,
R10) · database (R9, R10, R11, local Django checks) · URL shortening (V1 implementation and
docs, R16) · metadata extraction (R12, R20, R30) · frontend (R21, R22, R23) · security (R12–R16,
R8) · Git workflow (R25–R29). Every topic the prompt lists has at least one source above, or
an explicit limitation.
