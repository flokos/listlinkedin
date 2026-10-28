# ADR-007: Custom user, session auth with allauth headless, claim-based ownership migration

- Status: Accepted (2026-10-28, V2 planning)
- Related: [06 Ownership transition](../06-MIGRATION-PLAN.md#ownership-transition), [12](../12-AUTHORIZATION.md), [13](../13-SECURITY.md), [ADR-011](ADR-011-accounts-required-legacy-lists.md)

## Context

V2 introduces accounts. V1 has **no** `django.contrib.auth`, sessions or CSRF middleware and no
auth tables in any database (verified). Django's docs say to set `AUTH_USER_MODEL` before the
first migration, and that the model must be created in its app's first migration. Changing it
later "can't be done automatically" [R1]. The SPA is served from the same origin as the API
(nginx). V1 lists are owned by bearer tokens held in browsers.

## Decision

- **Custom user** `accounts.User(AbstractUser)` with `username` removed, email as the login
  identifier (unique, case-insensitive), and a `display_name`. It is created in
  `accounts/0001_initial` in the same PR that sets `AUTH_USER_MODEL` and installs contrib
  auth. Domain code references users by id only.
- **Authentication:** django-allauth in **headless browser mode** [R6]: Django session cookies
  plus CSRF, with endpoints under `/_allauth/browser/v1/`. It covers sign-up, login, logout,
  email verification, password reset, rate limits and enumeration prevention. DRF uses
  `SessionAuthentication` (CSRF enforced for authenticated requests [R8]) plus a legacy bearer
  authenticator for unclaimed V1 lists.
- **Ownership migration:** V1 lists become *legacy lists* (`owner_id NULL`, token hash kept,
  `unlisted`, expiry kept). A signed-in user **claims** one by presenting its token. The claim
  runs atomically under the list lock and retires the token. Nothing is assigned
  automatically. The legacy path is removed after the last legacy list expires.

## Alternatives considered

- **Built-in `auth.User` plus a profile model:** works, but is harder to change later. A
  custom user costs nothing now, since there are no tables yet.
- **JWT or token auth for the SPA:** tokens in JavaScript-readable storage add XSS impact and
  refresh logic. Same-origin cookies with CSRF are the simpler, standard Django choice.
- **Hand-written auth endpoints around `django.contrib.auth`:** feasible, but verification,
  reset, rate limiting and enumeration-safe responses are exactly what allauth already
  maintains (65.21.0, October 2026, supports Django 5.2–6.1 [R6]).
- **Automatic ownership assignment for V1 lists:** no reliable proof of identity. Forbidden by
  the prompt.

## Consequences

- The production `security.W003` silence is removed, and CSRF becomes part of every API test.
- New dependency: django-allauth. Pin it and read changelogs on upgrade.
- Email delivery (SMTP) becomes part of the deployment ([14](../14-INFRASTRUCTURE.md#email)).
- Setting names for allauth's headless mode must be checked against the official docs in task
  1.1. They were seen only through a docs mirror during planning ([19](../19-RESEARCH-REFERENCES.md)).
