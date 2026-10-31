# ADR-014: Stay on Django 5.2 LTS for V2; move to 6.2 LTS afterwards

- Status: Accepted (2026-10-28, V2 planning)
- Related: [14 Django and dependency versions](../14-INFRASTRUCTURE.md#django-and-dependency-versions)

## Context

V1 runs Django 5.2.18 (LTS, extended support until April 2028). Current releases are 6.0.9
and 6.1.2. 6.2 LTS is planned for April 2027 [R3]. Django 6.0 added a Tasks API (without a
production backend or worker) and built-in CSP support. It also changed the
`DEFAULT_AUTO_FIELD` default and requires Python ≥3.12 [R2]. V2 is a large change on its own.

## Decision

- Develop and launch V2 on **Django 5.2 LTS**. Get the Tasks API through the `django-tasks`
  backport [R4], and keep nginx as the CSP source.
- After V2 is stable, upgrade to **6.2 LTS** as its own project, well before April 2028.
- Minor dependency updates (for example DRF 3.16 → 3.18) are separate small PRs.

## Alternatives considered

- **Upgrade to 6.1 now:** two big changes at once. 6.1 support ends in December 2027, so a
  second upgrade to 6.2 would follow soon anyway.
- **Upgrade during V2 development:** it would interleave framework churn with feature work and
  complicate cherry-picks from `main`, which stays on 5.2.

## Consequences

- One framework version across `main` and `v2` until after the release, so V1 fixes port
  cleanly.
- django-tasks is a backport dependency until the 6.2 upgrade.
- Python stays at 3.13, which fits both 5.2 and 6.x. *Update 2026-10-31 (D33):* Python is 3.14,
  which Django 5.2 supports since 5.2.8 and 6.x supports too. The Django decision is unchanged.
