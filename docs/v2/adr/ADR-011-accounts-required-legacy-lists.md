# ADR-011: Accounts required to create lists; V1 lists become legacy lists

- Status: Accepted (2026-10-28. **Product owner decision**, asked during planning). **Carried
  out in full in task 9.6 (v2.1.0, 2026-10-31):** V1 was never deployed (D32), so no legacy list
  ever existed in production and the sunset followed `v2.0.0` directly; `sharing.0011` refuses
  to drop a live one.
- Related: [ADR-007](ADR-007-authentication-and-ownership-migration.md), [06 Ownership transition](../06-MIGRATION-PLAN.md#ownership-transition), [12](../12-AUTHORIZATION.md)

## Context

V1 lets anyone create a list anonymously and manage it with a secret token. V2 introduces
accounts, private lists, collaboration, groups and synced copies, all of which need an owner
identity. Two options were put to the product owner: keep anonymous "guest" lists alongside
accounts, or require an account to create lists while existing V1 lists keep working.

## Decision

- **Creating a list requires a signed-in account** (in the API and the UI).
  `POST /api/v1/lists/` answers 410 with an explanation.
- **Viewing stays anonymous** for `unlisted` and `public` lists.
- Existing V1 lists become **legacy lists**. They remain `unlisted`, keep their expiry, and
  are manageable with their edit link (V1-equivalent rights: content edits, delete, rotate)
  until they are **claimed** into an account or **expire**.
- Once the last legacy list has expired (≤30 days after launch plus the purge lag), the legacy
  code paths are removed (task 9.6).

## Alternatives considered

- **Keep guest lists alongside accounts:** maximum continuity, but two ownership models
  forever (tokens and accounts), every feature needing a "guest" variant, and a permanent
  anonymous-creation abuse surface. Rejected by the product owner.

## Consequences

- One ownership model in the long run, which simplifies authorization, groups and sync.
- Sign-up friction for people who only want a quick list, mitigated by a short sign-up
  (email + password) with verification needed only for public sharing.
- The V1 "no sign-up" promise in the UI copy must change (task 1.4).
- Legacy-list support is temporary code with a fixed end date.
