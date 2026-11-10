# ADR-020: Connected browsers: the extension signs in with an approved, long-lived session

- Status: Accepted (2026-11-10, user: D36). Extends
  [ADR-019](ADR-019-cross-origin-frontends.md): a connected browser's token is one of its
  session tokens, but it outlives ADR-019's two weeks.
- Related: [09 Session and account](../09-API-DESIGN.md#session-and-account),
  [12 Principals](../12-AUTHORIZATION.md#principals),
  [13 Sessions, cookies and headers](../13-SECURITY.md#sessions-cookies-and-headers),
  [21 Sessions](../21-SECURITY-REVIEW.md#sessions),
  [17 phase 11](../17-IMPLEMENTATION-ROADMAP.md#phase-11-browser-extension)

## Context

Phase 11 adds a browser extension for Chrome and Firefox. It saves pages into lists and copies
list and group links from a popup, a right-click menu or a keyboard shortcut, without the site
being open, so it must stay signed in for months. The user decided (D36):

- no password is typed into the extension: the user approves the browser on this site;
- a connected browser can do everything the account can;
- builds are installed by hand for now (no store), so the server can't rely on an extension ID
  that a store assigns.

Already there: session tokens in `X-Session-Token` with no CSRF token (ADR-019), and an
extension that has permission for this site calls it from its background script without CORS.
Missing: a way to give the extension such a token without a password, and a longer life for it.

## Decision

**A connected browser is an ordinary Django session**, signed in as the account, whose token
the extension sends as `X-Session-Token`. There is no new authentication scheme: the API's
two security schemes, the CSRF rules and everything that ends an account's sessions apply as
they are.

**Connecting** (the authorization-code idea with PKCE [RFC 7636], cut down to one site):

1. The extension makes a random verifier and opens
   `/connect-browser?challenge=<base64url(SHA-256(verifier))>&name=<label>` in a tab.
2. The page needs a signed-in user (sign-in first, then back). It asks the extension's content
   script, which runs on this site only, whether the extension started this request. Without
   that answer it shows no way to approve: a link someone sent connects nothing.
3. The user chooses **Connect**. `POST /api/v2/me/browsers/approvals/` accepts **this site's
   cookie session with its CSRF token only**, and answers with a one-time code valid for two
   minutes. The server keeps the code's SHA-256 and the challenge.
4. The page hands the code to the content script with `window.postMessage` to its own origin.
   The code is never in a URL, a log or on screen.
5. The extension calls `POST /api/v2/browsers/connect/` with the code and the verifier. The
   server locks the row, checks that the code is unused and unexpired, that the verifier
   matches the challenge and that the account can still sign in, creates the session with
   Django's `login()` and answers with its token, once. Every failure gets the same 400.

**Lifetime.** The session ends 90 days after its last use, and at the latest one year after
connecting. Use is recorded once a day (`browsers.touch_browser`, called by the token
authentication), which moves the end forward. Other session tokens keep Django's two weeks.

**Ending.** The user disconnects a browser on the account page, or the extension disconnects
itself: `DELETE /api/v2/me/browsers/{id}/` deletes the session. Deleting or suspending the
account deletes its connections; a password change invalidates them like every other session.
`GET /api/v2/me/browsers/` lists only connections whose session still works.

**Limits.** Ten browsers per account (pending approvals count). The exchange is rate-limited
per client IP (`browser_connect`, 30/hour). Each new connection emails the account.

**What a connected browser can't do:** approve another browser. Everything else on `/api/v2/`
and allauth's app client is open to it, as to any session token.

Storage: `accounts_connectedbrowser` holds the label, and either a pending approval (code
hash, challenge, expiry) or a connection (session key, connected and last-used times). A CHECK
allows no other state.

## Alternatives considered

- **Email and password in the extension's popup** (ADR-019's app client as it is): no backend
  work, but passwords typed into an extension and a sign-in every two weeks. Not chosen by the
  user.
- **A redirect to the extension** (`identity.launchWebAuthFlow`, as OAuth clients do): the
  server would have to allow-list each build's redirect address, which comes from the extension
  ID. Hand-installed builds have no stable ID, the two browsers form the address differently,
  and browser tests can't drive the flow. The content-script handover needs no ID: the code can
  only be picked up inside the user's own browser, and PKCE ties it to the extension that asked.
- **`externally_connectable` messaging** from the page to the extension: Chrome only.
- **A code the user types** (device flow): more steps, and the classic target of phishing.
- **A separate token table with hashed tokens** and its own `Authorization: Bearer` scheme:
  tokens would be hashed at rest, at the price of a second authentication path on every view,
  a third OpenAPI scheme, and "end all sessions" to implement again for each cause. Worth
  revisiting if tokens with narrower rights are ever wanted.
- **Narrower rights** (only what the extension needs): safer if a token is stolen, but the
  user chose full rights. Approval by cookie session only is the one limit kept.
- **No end at all**, or a longer `SESSION_COOKIE_AGE` for everyone: neither an inactivity nor
  a maximum lifetime would be left to document ([21](../21-SECURITY-REVIEW.md#sessions)).

## Consequences

- One table, four endpoints, one throttle scope, one page and an account section. No new
  dependency, service or scheduled job: stale rows go with the account's next approval.
- A connected browser's session key is stored in clear, in `django_session` like every session
  and in `accounts_connectedbrowser`. A database leak exposes it for up to a year instead of
  two weeks. Ending all sessions (rotate `DJANGO_SECRET_KEY`, or empty the session table) ends
  connections too.
- The token sits in the extension's own storage: readable by that extension, and by whoever
  controls the browser profile. A stolen token is worth a stolen session, minus approving
  other browsers.
- Users can now see and end these sessions (ASVS V7.5.2, partly: cookie sessions still aren't
  listed).
- The page and the extension share a small message protocol
  (`frontend/src/utils/extensionBridge.ts`). Both live in this repository and change together.
- Each connection sends one more email through the relay.
