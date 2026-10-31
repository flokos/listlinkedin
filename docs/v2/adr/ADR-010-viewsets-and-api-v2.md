# ADR-010: DRF ViewSets under `/api/v2/`; `/api/v1/` kept for the transition

- Status: Accepted (2026-10-28, V2 planning)
- Related: [09-API-DESIGN.md](../09-API-DESIGN.md), [01 discrepancy 1](../01-V1-AUDIT.md#discrepancies-between-the-prompts-intended-v1-and-the-real-v1)

## Context

The prompt says V1 uses DRF ViewSets and asks V2 to keep using them. V1 actually uses
**APIView** classes. V2's API differs from V1 in ways that break compatibility: authentication
(sessions instead of only bearer tokens), creation now requires an account, list visibility,
link ordering and new representations. External curl users of `/api/v1/` exist (the README
documents them), and V1 edit links must keep working during the transition.

## Decision

- New endpoints live under **`/api/v2/`** and are built from **ViewSets** with routers and
  `@action`s (fork, branches, sync, restore, reorder, claim, image). Nested resources (links,
  members, revisions, exclusions) use explicit routes onto ViewSets, so no nested-router
  dependency is needed.
- `/api/v1/` stays during the transition with V1 representations and ordering. It delegates to
  the same services. Creation answers 410. Reads respect visibility. Writes accept legacy
  tokens on unclaimed lists only. It is removed at the legacy sunset (task 9.6).
- Responses keep DRF's error shapes (which the frontend already parses) and add a stable `code`.

## Alternatives considered

- **Extending `/api/v1/` in place:** the semantic changes (auth, visibility, ordering) would
  silently break existing clients.
- **Keeping APIViews for v2:** works, but the prompt asks for ViewSets, and they give standard
  routing and permission hooks for the many actions V2 adds.
- **Header-based versioning:** less visible, harder to route in nginx, and unnecessary.

## Consequences

- Two URL namespaces for a while. Their behaviour is pinned by tests on both.
- The OpenAPI schema is generated per version. The frontend uses v2 only, with generated types.
