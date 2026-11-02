# ADR-019: Frontends on other domains: CORS without credentials, allauth app-client tokens

- Status: Accepted (2026-11-02, user). Supersedes the "SPA on the same origin only" part of
  [ADR-007](ADR-007-authentication-and-ownership-migration.md); its custom user and cookie
  sessions for this site's SPA stand.
- Related: [09 Conventions](../09-API-DESIGN.md#conventions), [13 Sessions, cookies and headers](../13-SECURITY.md#sessions-cookies-and-headers), [21](../21-SECURITY-REVIEW.md), [deployment](../../deployment.md)

## Context

A teammate is building a second frontend for the same API, hosted on their own domain
(`https://fe.acv.gr`), while the API stays on this site's server. V2 was same-origin only: no
CORS headers, and sign-in by a `SameSite=Lax`, host-only (`__Host-`) session cookie with CSRF.
A page on another *site* can't use that: browsers don't send `SameSite=Lax` cookies on its
`fetch()` calls, and Safari and Firefox block third-party cookies whatever `SameSite` says.
Loosening the cookie (`SameSite=None`, credentialed CORS) would also expose this site's own
sessions to every allowed origin's scripts.

## Decision

- **Sign-in for other frontends** uses django-allauth's headless **`app` client**
  (`/_allauth/app/v1/`). Signing in returns a `session_token`; the frontend sends it as
  `X-Session-Token` on every request. The API accepts it through `SessionTokenAuthentication`
  (allauth's `XSessionTokenAuthentication`), next to the cookie session on every `/api/v2/`
  view except `/r/`, which browsers open by navigation, without headers.
- The token is the key of an ordinary **Django session**, so signing out, `sessions_revoked_at`
  (account deletion), suspension and erasure end it on the next request, as they end cookie
  sessions. A deleted account's token works only where its cookie session does (session check,
  restore). Writes need no CSRF token: browsers never add the header by themselves.
- **CORS** (django-cors-headers) answers only origins listed in `CORS_ALLOWED_ORIGINS`
  (empty by default: no CORS at all), only on `/api/v2/` and `/_allauth/app/v1/`, and
  **without credentials**: no `Access-Control-Allow-Credentials`, so browsers never send this
  site's cookies cross-origin. Allowed request headers: `accept`, `content-type`,
  `x-session-token`; exposed: `X-Request-ID`. Origins are validated at startup: https, no path,
  no wildcard (plain http only for `localhost`/`127.0.0.1`, for development).
- **Opaque session tokens, not JWTs.** One backend checks every token, so a stateless token
  gains nothing, and revocation must be immediate (suspension, deletion).
- Account emails (verification, password reset) still link to this site's pages
  (`PUBLIC_BASE_URL`). Users of another frontend finish those steps here.

## Alternatives considered

- **Credentialed CORS with the session cookie** (`SameSite=None`, `CORS_ALLOW_CREDENTIALS`):
  third-party cookies are blocked by Safari and Firefox, and every allowed origin's scripts
  would act with this site's sessions; CSRF would depend on the origin list.
- **allauth's JWT strategy** (`Authorization: Bearer` access and refresh tokens): revocation
  waits for the access token to expire, and it adds a signing key to manage and a refresh flow
  for every client.
- **A proxy on the other domain** forwarding `/api/` here: avoids CORS but puts a third party's
  server in the path of every password and session.
- **A subdomain of this site** (same site, so `SameSite=Lax` cookies would work): not where the
  teammate hosts.

## Consequences

- New dependency: django-cors-headers (4.9).
- The token lives in the other frontend's JavaScript: an XSS on that site can steal it. That
  site's own CSP and code are its owner's responsibility; tokens end at sign-out or after the
  session age (two weeks).
- The OpenAPI schema declares `SessionToken` (header `X-Session-Token`) next to
  `SessionCookie`. Neither grants anything but an account's own role (invariant 7).
- Adding or removing an origin is an `.env` change (`CORS_ALLOWED_ORIGINS`) and a restart.
