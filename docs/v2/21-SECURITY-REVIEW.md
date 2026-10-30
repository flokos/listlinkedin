# 21: Security review (task 9.1)

A review of V2 against the **OWASP Application Security Verification Standard 5.0.0**, levels 1 and 2 [R14], done on 2026-10-30 before the release. Every L1 and L2 requirement is listed below with its status and the evidence: a file, a test or another document. The requirement texts are abridged from ASVS 5.0.0 (© OWASP Foundation, CC BY-SA 4.0, [the standard](https://github.com/OWASP/ASVS/tree/v5.0.0/5.0)); read the standard for the full wording.

| Status | Meaning | L1 | L2 | Total |
|---|---|---|---|---|
| Pass | Met before this review | 50 | 81 | 131 |
| Fixed | Met by a change in task 9.1 | 6 | 18 | 24 |
| Accepted | Not met: a documented decision, listed below | 1 | 16 | 17 |
| N/A | The feature isn't in the application | 13 | 68 | 81 |
| | | 70 | 183 | 253 |

## Changes made by this review

- **API documentation from this origin.** `/api/docs/` loaded Swagger UI from a CDN, unpinned (`swagger-ui-dist@latest`), onto our origin, where a compromised script could have acted for the signed-in user. Its files now come from the `drf-spectacular-sidecar` package, served by the api (`config/docs.py`), and the page has a CSP that allows only this origin. The unused `/api/redoc/` page is gone.
- **Headers.** API answers carry `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` and `Cache-Control: no-store`; media gained `frame-ancestors 'none'`; the app's files declare UTF-8 and send `Cross-Origin-Opener-Policy` and a `Permissions-Policy`.
- **Cookies.** In production the session and CSRF cookies are `__Host-sessionid` and `__Host-csrftoken` (the app and the e2e helpers read either CSRF name).
- **Plain HTTP.** API and account requests over HTTP answer 403 instead of being redirected, so a client that sent a secret in the clear notices.
- **Passwords.** No composition rule (all-digit passwords are allowed; common ones are still refused), the site's name is refused, and reset links last one hour, not three days. Sign-ups are limited to 10/h per IP, as [13](13-SECURITY.md#rate-limits) already said.
- **Logging.** A request id from nginx on every log line of both, the user id on every api record, JSON lines in production, a log of authentication events, rotation of container logs, and a test that no secret or email address is ever logged.
- **Browser memory.** Lists cached for quick revisits are dropped when the user signs out or changes.
- **Dependencies.** `pip-audit` and `npm audit` run in CI; Dependabot is configured.
- **Lint.** `v-html` is a lint error (it was a warning, and warnings don't fail the lint).
- Doc fixes: `SENTRY_DSN` was listed in [14](14-INFRASTRUCTURE.md) but nothing read it; it is now described as an option a deployment can add. A V1 docstring in `sharing/permissions.py` still said there are no accounts.

## Accepted deviations

Requirements V2 doesn't meet, on purpose. Each is revisited after launch or when its condition changes.

| Requirement | Decision |
|---|---|
| V3.7.2 (L2) | `/r/` short URLs redirect to destinations users chose: that is the product. Destinations are validated http(s) URLs, blockable with `BLOCKED_DESTINATION_HOSTS`, and a short URL never bypasses its list's visibility (invariant 2). `next` parameters are same-origin only |
| V5.4.3 (L2) | No antivirus scan. Every image is decoded and re-encoded, so uploaded bytes are never served, and no other file type is accepted |
| V6.2.12 (L2) | No breached-password check: it would make the api call an outside service (such as Have I Been Pwned), and the api makes no outbound calls by design. The common-password list stands in. Revisit after launch |
| V6.3.3 (L2) | No multi-factor authentication yet ([Q6](20-DECISIONS-AND-OPEN-QUESTIONS.md)); allauth can add TOTP or passkeys by configuration |
| V7.3.1 (L2) | No inactivity timeout, by decision ([Sessions](#sessions)) |
| V7.5.2 (L2) | No list of active sessions to review; changing the password signs out every other device. Revisit with Q6 |
| V11.5.1 (L2) | Owner tokens have 256 bits and session keys about 165, but list, group and short codes have 96 bits: V1's format, which invariant 1 keeps. Guessing is online only, rate-limited, and a private list also needs membership |
| V12.3.1 (L2) | nginx → api and api → PostgreSQL stay on the host's private compose network, unencrypted. SMTP uses STARTTLS by default; the fetcher validates TLS. Revisit if services leave the single host |
| V12.3.3 (L2) | As V12.3.1 |
| V13.2.2 (L2) | The containers run as non-root users, but the app connects as the database owner the postgres image creates (a superuser). A least-privilege role is recommended in the deployment guide (task 9.4) |
| V13.2.4 (L2) | The worker reaches the public internet with private and metadata ranges denied ([13](13-SECURITY.md#ssrf-safe-fetcher)): fetching any public page is the feature. The api makes no outbound HTTP calls |
| V13.2.5 (L2) | As V13.2.4 |
| V13.3.1 (L2) | Secrets live in the host's `.env` and reach containers as environment variables; no vault on a single host |
| V13.3.2 (L2) | Only the deploying user should read `.env` (`chmod 600`, deployment guide in task 9.4) |
| V14.2.1 (L1) | Tokens and keys travel in headers or URL fragments, never in paths or queries. List and short codes are capabilities in URLs by design, protected by `no-referrer` and `noindex` |
| V14.3.3 (L2) | `localStorage` holds legacy lists' edit-link tokens (bearer credentials like a session token, V1's design) and preferences; removed with task 9.6 |
| V16.4.3 (L2) | Logs aren't shipped to a separate system yet; the deployment guide (task 9.4) recommends a log driver or collector |

## Context-specific words

Passwords may not contain the service's name, `listlinkedin`, in any case or spacing (`apps/accounts/validators.py`). Django's `UserAttributeSimilarityValidator` also refuses passwords too similar to the account's email address.

## Sessions

- Server-side Django sessions in PostgreSQL. The cookie is `HttpOnly`, `Secure`, `SameSite=Lax` and, in production, `__Host-sessionid`.
- **Lifetime:** 14 days (Django's default) from sign-in or the session's last change; requests alone don't extend it. **No inactivity timeout**: lists hold links, not money or health data, and people use the app across days; signing out is one click away, and password changes, account deletion and suspension end every session at once.
- **Parallel sessions:** unlimited. Changing the password signs out every other device.
- **Ending all sessions** (an operator action, e.g. after a leak of the signing key): rotate `DJANGO_SECRET_KEY`, or empty the session table: `docker compose -f compose.prod.yaml exec api python manage.py shell -c "from django.contrib.sessions.models import Session; Session.objects.all().delete()"`.

## Cryptographic inventory

| What | Algorithm | Key or secret | Lifecycle |
|---|---|---|---|
| Passwords | PBKDF2-SHA256, 1,000,000 iterations (Django 5.2) | per-password salt | Rehashed on sign-in when Django raises the cost |
| Sessions, CSRF, email verification and reset links | HMAC-SHA256 (Django signing) | `DJANGO_SECRET_KEY` (50 random characters) | Rotate by moving the old key to `SECRET_KEY_FALLBACKS`; reset links expire in 1 hour, verification in 3 days |
| Legacy edit links | 256-bit random token; SHA-256 hash stored | the token itself | Retired when claimed or rotated; all removed by task 9.6 |
| List, group and short codes | 96-bit random (`secrets`) | none | Permanent (invariant 1) |
| Media file names | SHA-256 of the re-encoded image | none | Immutable |
| TLS | TLS 1.2/1.3, ECDHE with AES-GCM or ChaCha20-Poly1305 | certificate key on the host (`TLS_CERT_DIR`) | Let's Encrypt, renewed every 60–90 days |
| Database | none (private compose network) | `POSTGRES_PASSWORD` | Set at installation; change with `ALTER ROLE` and `.env` |
| Mail relay | STARTTLS (`EMAIL_USE_TLS`) | `EMAIL_HOST_PASSWORD` | The relay's policy |

Secrets live only in the host's `.env` and reach the containers as environment variables. None is in the repository, an image or a log.

## Data classification

| Class | Data | Protection |
|---|---|---|
| Secret | Passwords, session keys, CSRF tokens, verification and reset keys, edit-link tokens, `DJANGO_SECRET_KEY` and other credentials | Never logged (tested) or returned again; hashed (passwords, edit links); keys in URL fragments only; HTTPS only |
| Personal | Email addresses, display names, reports' details, IP addresses (rate limiting, nginx log) | Email addresses shown only to their own account and never logged; display names shown to people sharing a list; erased 30 days after an account is deleted ([ADR-016](adr/ADR-016-account-deletion-grace-period.md)); reports go only to the operator |
| Restricted content | Private lists and groups, unlisted ones (by their code), history, members | The policy and SQL-filtered queries ([12](12-AUTHORIZATION.md)); `no-store`; never in the directory |
| Public content | Public lists and groups, tags, fetched page details | Anyone may read; still `noindex` |

Retention: lists live until they expire or are deleted; revisions live as long as their list ([Q2](20-DECISIONS-AND-OPEN-QUESTIONS.md)); expired lists are purged daily; media no list uses is removed weekly; logs rotate after 5 × 20 MB per container.

## Logging

| Source | What | Format | Where |
|---|---|---|---|
| nginx | Every request: address, request line, status, size, user agent, `request_id` | `requests` log format | Container output, rotated |
| api | Application events (ids only), authentication events (`apps.accounts.auth`), every 4xx and 5xx (`django.request`), operator and moderation actions, queued tasks | JSON lines in production (time in UTC, level, logger, message, `request_id`, `user_id`); text in development | Container output, rotated |
| worker | Task runs, fetch results and failures | Same as the api; `request_id` is `-` (the api's line for the queued task links them) | Container output, rotated |
| cleanup | Scheduled jobs' results | Same as the api | Container output, rotated |
| PostgreSQL | Errors and slow statements (image defaults) | PostgreSQL's | Container output, rotated |

Never logged: passwords, session or CSRF values, keys, edit-link tokens, email addresses, reports' details (`tests/test_logging.py`). Only root and the docker group read container logs on the host. Shipping them to a separate system is accepted as not yet done (V16.4.3).

## Dependencies

- **Audit (2026-10-30):** `pip-audit` on `backend/uv.lock` and `npm audit` for `frontend/` and `e2e/`: no known vulnerabilities.
- **In CI:** the `checks` job runs `pip-audit` (any advisory with a fix fails it) and `npm audit --audit-level=high` on every push and pull request.
- **Dependabot** (`.github/dependabot.yml`): weekly grouped updates for Python, both npm projects, the Docker base images and the GitHub Actions; security updates as soon as an advisory appears. GitHub reads the file from the default branch, so it starts working once V2 is on `main`.
- **Remediation times:** critical or high with a fix: within 7 days of the advisory. Others: with the next weekly update. An advisory without a fix that CI flags is ignored explicitly (`--ignore-vuln` with a comment) and added to this document with a review date.

## V1 regression checklist

Reviewed against [15](15-TEST-STRATEGY.md#v1-regression-checklist) (risk 30): every test file it names still exists and runs in CI (`test_shortener.py`, `test_links.py`, `test_lists.py`, `test_security.py`, `test_domain.py`, `test_expiration.py`, `tests/integration/test_workflow.py`; `client.test.ts`, `useOwnedLists`, `useEditLink`, backup, url, time and `LinkForm` tests; the listed e2e specs). Behaviour V2 changed on purpose is recorded there with its decision. V1's `no-store` on `/r/` is kept: the new `no_store` middleware leaves an existing `Cache-Control` alone.

## Requirements

### V1 Encoding and Sanitization

| ID | L | Requirement (abridged) | Status | Evidence |
|---|---|---|---|---|
| V1.1.1 | 2 | Input is decoded or unescaped into a canonical form only once, it … | Pass | Django and DRF decode request bodies once (JSON, form, multipart parsers); serializers validate the decoded values |
| V1.1.2 | 2 | The application performs output encoding and escaping either as a final step … | Pass | Vue escapes at render time; DRF's JSON renderer; ORM parameters |
| V1.2.1 | 1 | Output encoding for an HTTP response, HTML document, or XML document is … | Pass | Vue text interpolation only; JSON responses; headers set by Django |
| V1.2.2 | 1 | When dynamically building URLs, untrusted data is encoded according to its context … | Pass | Path parts encoded (`enc()` in `frontend/src/api/*.ts`); link targets are http(s) only (`normalize_destination_url`) or our `/r/` URLs |
| V1.2.3 | 1 | Output encoding or escaping is used when dynamically building JavaScript content (including … | Pass | JSON is produced by DRF or `json.dumps`, never by string building |
| V1.2.4 | 1 | Data selection or database queries (e.g., SQL, HQL, NoSQL, Cypher) use parameterized … | Pass | ORM everywhere; the one raw query (`groups/selectors.popular_tags`) takes parameters |
| V1.2.5 | 1 | The application protects against OS command injection and that operating system calls … | Pass | No OS commands in application code |
| V1.2.6 | 2 | The application protects against LDAP injection vulnerabilities, or that specific security controls … | N/A | No LDAP |
| V1.2.7 | 2 | The application is protected against XPath injection attacks by using query parameterization … | N/A | No XPath |
| V1.2.8 | 2 | LaTeX processors are configured securely (such as not using the "--shell-escape" flag) … | N/A | No LaTeX |
| V1.2.9 | 2 | The application escapes special characters in regular expressions (typically using a backslash) … | Pass | No regular expressions are built from input: search uses PostgreSQL full text and trigrams, list search uses substring matching |
| V1.3.1 | 1 | All untrusted HTML input from WYSIWYG editors or similar is sanitized using … | N/A | No HTML input: titles and descriptions are plain text |
| V1.3.2 | 1 | The application avoids the use of eval() or other dynamic code execution … | Pass | No `eval` or dynamic code; the CSPs have no `'unsafe-eval'` |
| V1.3.3 | 2 | Data being passed to a potentially dangerous context is sanitized beforehand to … | Pass | Values put into other contexts are reduced first, e.g. a report's subject is one line (`sharing/services/moderation.py`); file names are generated |
| V1.3.4 | 2 | User-supplied Scalable Vector Graphics (SVG) scriptable content is validated or sanitized to … | Pass | SVG is refused for uploads and fetched icons (`metadata/images.py`, `metadata/parser.py`) |
| V1.3.5 | 2 | The application sanitizes or disables user-supplied scriptable or expression template language content … | N/A | No markup, template or style languages are accepted from users |
| V1.3.6 | 2 | The application protects against Server-side Request Forgery (SSRF) attacks, by validating untrusted … | Pass | The SSRF-safe fetcher ([13](13-SECURITY.md#ssrf-safe-fetcher)), in the worker only |
| V1.3.7 | 2 | The application protects against template injection attacks by not allowing templates to … | Pass | Templates are files; none is built from input |
| V1.3.8 | 2 | The application appropriately sanitizes untrusted input before use in Java Naming and … | N/A | No JNDI |
| V1.3.9 | 2 | The application sanitizes content before it is sent to memcache to prevent … | N/A | No memcache; the database cache keys are built from a scope and a client id |
| V1.3.10 | 2 | Format strings which might resolve in an unexpected or malicious way when … | Pass | Log calls pass input as arguments, never as the format string |
| V1.3.11 | 2 | The application sanitizes user input before passing to mail systems to protect … | Pass | Django refuses line breaks in mail headers; recipients are fixed; report subjects are one line |
| V1.4.1 | 2 | The application uses memory-safe string, safer memory copy and pointer arithmetic to … | Pass | Memory-safe runtimes (Python, JavaScript). Native image decoding (Pillow) runs behind size and pixel limits and is kept current (dependency audit) |
| V1.4.2 | 2 | Sign, range, and input validation techniques are used to prevent integer overflows. | Pass | Python integers don't overflow; sizes and counts are bounded (uploads, links, tags) |
| V1.4.3 | 2 | Dynamically allocated memory and resources are released, and that references or pointers … | Pass | Managed memory |
| V1.5.1 | 1 | The application configures XML parsers to use a restrictive configuration and that … | N/A | No XML parsing: pages are parsed with `html.parser`, SVG is refused |
| V1.5.2 | 2 | Deserialization of untrusted data enforces safe input handling, such as using an … | Pass | JSON only; sessions use Django's JSON serializer; nothing from requests is unpickled |

### V2 Validation and Business Logic

| ID | L | Requirement (abridged) | Status | Evidence |
|---|---|---|---|---|
| V2.1.1 | 1 | The application's documentation defines input validation rules for how to check the … | Pass | [09](09-API-DESIGN.md) field rules, [04](04-DOMAIN-MODEL.md) value objects |
| V2.1.2 | 2 | The application's documentation defines how to validate the logical and contextual consistency … | Pass | [04](04-DOMAIN-MODEL.md#invariants) invariants (L1–L3, K1–K5, G1) |
| V2.1.3 | 2 | Expectations for business logic limits and validations are documented, including both per-user … | Pass | Limits in [04](04-DOMAIN-MODEL.md) (100 links, 100 lists per group, 10 tags) and [13](13-SECURITY.md#rate-limits) |
| V2.2.1 | 1 | Input is validated to enforce business or functional expectations for that input … | Pass | Serializers with allowlists: choice fields, `normalize_destination_url`, `normalize_tags` |
| V2.2.2 | 1 | The application is designed to enforce input validation at a trusted service … | Pass | Every rule is enforced by the API; the frontend's `LIMITS` only give early hints |
| V2.2.3 | 2 | The application ensures that combinations of related data items are reasonable according … | Pass | Database CHECKs (legacy lists unlisted and expiring, tombstones without positions) and service rules |
| V2.3.1 | 1 | The application will only process business logic flows for the same user … | Pass | Claiming needs a session and the token; restore needs `If-Match`; verification and reset keys are single-use |
| V2.3.2 | 2 | Business logic limits are implemented per the application's documentation to avoid business … | Pass | Caps enforced under row locks (links per list, lists per group), with concurrency tests |
| V2.3.3 | 2 | Transactions are being used at the business logic level such that either … | Pass | Services are atomic; a content change and its revision commit together (invariant 3) |
| V2.3.4 | 2 | Business logic level locking mechanisms are used to ensure that limited quantity … | Pass | Row locks for positions and caps; idempotency keys for creating and copying |
| V2.4.1 | 2 | Anti-automation controls are in place to protect against excessive calls to application … | Pass | A rate limit on every write and costly read ([13](13-SECURITY.md#rate-limits)), allauth's limits |

### V3 Web Frontend Security

| ID | L | Requirement (abridged) | Status | Evidence |
|---|---|---|---|---|
| V3.2.1 | 1 | Security controls are in place to prevent browsers from rendering content or … | Pass | API answers are JSON with `nosniff` and a CSP that allows nothing; media is WebP only with a sandbox CSP |
| V3.2.2 | 1 | Content intended to be displayed as text, rather than rendered as HTML … | Fixed | Text is rendered by Vue's interpolation; `vue/no-v-html` is now an error, not a warning (`frontend/eslint.config.js`) |
| V3.3.1 | 1 | Cookies have the 'Secure' attribute set, and if the '\__Host-' prefix is … | Fixed | All cookies are `Secure` in production and now named `__Host-sessionid` and `__Host-csrftoken` (`config/settings/production.py`) |
| V3.3.2 | 2 | Each cookie's 'SameSite' attribute value is set according to the purpose of … | Pass | `SameSite=Lax` on both cookies |
| V3.3.3 | 2 | Cookies have the '__Host-' prefix for the cookie name unless they are … | Fixed | As V3.3.1 |
| V3.3.4 | 2 | If the value of a cookie is not meant to be accessible … | Pass | The session cookie is `HttpOnly` (Django) and only ever set by `Set-Cookie`. The CSRF cookie is readable on purpose (the SPA echoes it) |
| V3.4.1 | 1 | A Strict-Transport-Security header field is included on all responses to enforce an … | Pass | HSTS for a year with `includeSubDomains`: Django on its answers, nginx on the app and media |
| V3.4.2 | 1 | The Cross-Origin Resource Sharing (CORS) Access-Control-Allow-Origin header field is a fixed value … | Pass | No CORS headers: same-origin only |
| V3.4.3 | 2 | HTTP responses include a Content-Security-Policy response header field which defines directives to … | Fixed | App: nginx CSP. API answers: `default-src 'none'` (`config.middleware.content_security_policy`, new). Docs page: own-origin CSP (`config/docs.py`, new). Media: sandbox |
| V3.4.4 | 2 | All HTTP responses contain an 'X-Content-Type-Options: nosniff' header field. This instructs browsers … | Pass | `nosniff` on Django's answers (`SECURE_CONTENT_TYPE_NOSNIFF`) and nginx's |
| V3.4.5 | 2 | The application sets a referrer policy to prevent leakage of technically sensitive … | Pass | `Referrer-Policy: no-referrer` everywhere |
| V3.4.6 | 2 | The web application uses the frame-ancestors directive of the Content-Security-Policy header field … | Fixed | `frame-ancestors 'none'` now also on API answers, the docs page and media (the app had it) |
| V3.5.1 | 1 | Verify that, if the application does not rely on the CORS preflight mechanism to … | Pass | Django's CSRF check on every session-authenticated write; bearer tokens aren't sent automatically; anonymous writes (reports) carry no authority |
| V3.5.2 | 1 | Verify that, if the application relies on the CORS preflight mechanism to prevent disallowed … | N/A | Nothing relies on CORS preflight |
| V3.5.3 | 1 | HTTP requests to sensitive functionality use appropriate HTTP methods such as POST … | Pass | Changes only through POST, PATCH, PUT and DELETE |
| V3.5.4 | 2 | Separate applications are hosted on different hostnames to leverage the restrictions provided … | Pass | One application per host name. Uploaded media is served from the same origin as inert files with a sandbox CSP ([ADR-012](adr/ADR-012-media-and-images.md)) |
| V3.5.5 | 2 | Messages received by the postMessage interface are discarded if the origin of … | N/A | No `postMessage` |
| V3.7.1 | 2 | The application only uses client-side technologies which are still supported and considered … | Pass | No plugins or deprecated client technology |
| V3.7.2 | 2 | The application will only automatically redirect the user to a different hostname … | Accepted | `/r/` short URLs redirect to destinations users chose: that is the product. Destinations are validated http(s) URLs, blockable with `BLOCKED_DESTINATION_HOSTS`, and a short URL never bypasses its list's visibility (invariant 2). `next` parameters are same-origin only |

### V4 API and Web Service

| ID | L | Requirement (abridged) | Status | Evidence |
|---|---|---|---|---|
| V4.1.1 | 1 | Every HTTP response with a message body contains a Content-Type header field … | Fixed | The app's HTML, JavaScript and CSS now declare UTF-8 (nginx `charset`); Django's HTML, CSS and JS do; JSON is UTF-8 by definition (RFC 8259 defines no charset parameter) |
| V4.1.2 | 2 | Only user-facing endpoints (intended for manual web-browser access) automatically redirect from HTTP … | Fixed | Plain-HTTP requests to `/api/` and `/_allauth/` now answer 403 instead of redirecting (nginx); pages still redirect |
| V4.1.3 | 2 | Any HTTP header field used by the application and set by an … | Pass | nginx overwrites `X-Forwarded-For`, `X-Forwarded-Proto` and `X-Request-ID`; DRF trusts exactly one proxy |
| V4.2.1 | 2 | All application components (including load balancers, firewalls, and application servers) determine boundaries … | Pass | nginx is the only entry point; it proxies to Gunicorn with HTTP/1.0 and no connection reuse (its default), so it decides message boundaries |
| V4.3.1 | 2 | A query allowlist, depth limiting, amount limiting, or query cost analysis is … | N/A | No GraphQL |
| V4.3.2 | 2 | GraphQL introspection queries are disabled in the production environment unless the GraphQL … | N/A | No GraphQL |
| V4.4.1 | 1 | WebSocket over TLS (WSS) is used for all WebSocket connections. | N/A | No WebSockets (only Vite's development server uses one) |
| V4.4.2 | 2 | Verify that, during the initial HTTP WebSocket handshake, the Origin header field is checked … | N/A | No WebSockets |
| V4.4.3 | 2 | Verify that, if the application's standard session management cannot be used, dedicated tokens are … | N/A | No WebSockets |
| V4.4.4 | 2 | Dedicated WebSocket session management tokens are initially obtained or validated through the … | N/A | No WebSockets |

### V5 File Handling

| ID | L | Requirement (abridged) | Status | Evidence |
|---|---|---|---|---|
| V5.1.1 | 2 | The documentation defines the permitted file types, expected file extensions, and maximum … | Pass | [09](09-API-DESIGN.md#uploads) and [ADR-012](adr/ADR-012-media-and-images.md) |
| V5.2.1 | 1 | The application will only accept files of a size which it can … | Pass | 2 MB and 16 megapixels (Django), 3 MB on the upload routes (nginx) |
| V5.2.2 | 1 | When the application accepts a file, either on its own or within … | Pass | The type is identified from the content, the name is ignored, and the file is stored as a re-encoded WebP |
| V5.2.3 | 2 | The application checks compressed files (e.g., zip, gz, docx, odt) against maximum … | N/A | No archives are accepted; image decompression bombs are stopped by the pixel limit |
| V5.3.1 | 1 | Files uploaded or generated by untrusted input and stored in a public … | Pass | nginx serves media as files, typed only as WebP; nothing under `/media/` is ever executed |
| V5.3.2 | 1 | When the application creates file paths for file operations, instead of user-submitted … | Pass | Paths are content hashes |
| V5.4.1 | 2 | The application validates or ignores user-submitted filenames, including in a JSON, JSONP … | Pass | Uploaded file names are ignored; images are shown inline, never downloaded |
| V5.4.2 | 2 | File names served (e.g., in HTTP response header fields or email attachments) … | N/A | No file names are served |
| V5.4.3 | 2 | Files obtained from untrusted sources are scanned by antivirus scanners to prevent … | Accepted | No antivirus scan. Every image is decoded and re-encoded, so uploaded bytes are never served, and no other file type is accepted |

### V6 Authentication

| ID | L | Requirement (abridged) | Status | Evidence |
|---|---|---|---|---|
| V6.1.1 | 1 | Application documentation defines how controls such as rate limiting, anti-automation, and adaptive … | Pass | [13](13-SECURITY.md#rate-limits): allauth's failed sign-in limits per IP and per account, and sign-ups limited to 10/h per IP |
| V6.1.2 | 2 | A list of context-specific words is documented in order to prevent their … | Fixed | Context-specific words: the service's name ([Context-specific words](#context-specific-words)) |
| V6.1.3 | 2 | Verify that, if the application includes multiple authentication pathways, these are all documented together … | Pass | Two ways in, both documented: account sign-in with a password, and legacy edit links that only work on V1 lists until task 9.6 ([12](12-AUTHORIZATION.md#principals), [ADR-011](adr/ADR-011-accounts-required-legacy-lists.md)) |
| V6.2.1 | 1 | User set passwords are at least 8 characters in length although a … | Pass | At least 8 characters (`MinimumLengthValidator`) |
| V6.2.2 | 1 | Users can change their password. | Pass | Account page → Password |
| V6.2.3 | 1 | Password change functionality requires the user's current and new password. | Pass | allauth's password change needs the current password |
| V6.2.4 | 1 | Passwords submitted during account registration or password change are checked against an … | Pass | Django's `CommonPasswordValidator` (about 20,000 common passwords) |
| V6.2.5 | 1 | Passwords of any composition can be used, without rules limiting the type … | Fixed | Django's `NumericPasswordValidator` (no all-digit passwords) is removed: no composition rules |
| V6.2.6 | 1 | Password input fields use type=password to mask the entry. Applications may allow … | Pass | `PasswordField` is `type=password`, with a show toggle |
| V6.2.7 | 1 | "paste" functionality, browser password helpers, and external password managers are permitted. | Pass | Pasting allowed; `autocomplete` is `current-password` or `new-password` |
| V6.2.8 | 1 | The application verifies the user's password exactly as received from the user … | Pass | Django hashes the password exactly as sent |
| V6.2.9 | 2 | Passwords of at least 64 characters are permitted. | Pass | No maximum length (tested with 128 characters) |
| V6.2.10 | 2 | A user's password stays valid until it is discovered to be compromised … | Pass | No forced rotation |
| V6.2.11 | 2 | The documented list of context specific words is used to prevent easy … | Fixed | `apps/accounts/validators.py` (`ContextWordsValidator`) |
| V6.2.12 | 2 | Passwords submitted during account registration or password changes are checked against a … | Accepted | No breached-password check: it would make the api call an outside service (such as Have I Been Pwned), and the api makes no outbound calls by design. The common-password list stands in. Revisit after launch |
| V6.3.1 | 1 | Controls to prevent attacks such as credential stuffing and password brute force … | Pass | allauth: failed sign-ins 10/min per IP and 5 per 5 minutes per account; sign-ups 10/h per IP (new in 9.1, tested) |
| V6.3.2 | 1 | Default user accounts (e.g., "root", "admin", or "sa") are not present in … | Pass | No default accounts; Django admin isn't installed |
| V6.3.3 | 2 | Either a multi-factor authentication mechanism or a combination of single-factor authentication mechanisms … | Accepted | No multi-factor authentication yet ([Q6](20-DECISIONS-AND-OPEN-QUESTIONS.md)); allauth can add TOTP or passkeys by configuration |
| V6.3.4 | 2 | Verify that, if the application includes multiple authentication pathways, there are no undocumented pathways … | Pass | No other pathways (V6.1.3) |
| V6.4.1 | 1 | System generated initial passwords or activation codes are securely randomly generated, follow … | Pass | No generated passwords. Verification keys are signed and expire in 3 days (allauth); reset links work once and now for one hour (`PASSWORD_RESET_TIMEOUT`, was 3 days) |
| V6.4.2 | 1 | Password hints or knowledge-based authentication (so-called "secret questions") are not present. | Pass | No hints or security questions |
| V6.4.3 | 2 | A secure process for resetting a forgotten password is implemented, that does … | Pass | Reset by an emailed link whose key travels in the fragment; there is no second factor to bypass |
| V6.4.4 | 2 | If a multi-factor authentication factor is lost, evidence of identity proofing is … | N/A | No second factors |
| V6.5.1 | 2 | Lookup secrets, out-of-band authentication requests or codes, and time-based one-time passwords (TOTPs) … | N/A | No lookup secrets, one-time codes or TOTP |
| V6.5.2 | 2 | Verify that, when being stored in the application's backend, lookup secrets with less than … | N/A | As V6.5.1 |
| V6.5.3 | 2 | Lookup secrets, out-of-band authentication code, and time-based one-time password seeds, are generated … | N/A | As V6.5.1 |
| V6.5.4 | 2 | Lookup secrets and out-of-band authentication codes have a minimum of 20 bits … | N/A | As V6.5.1 |
| V6.5.5 | 2 | Out-of-band authentication requests, codes, or tokens, as well as time-based one-time passwords … | N/A | As V6.5.1 |
| V6.6.1 | 2 | Authentication mechanisms using the Public Switched Telephone Network (PSTN) to deliver One-time … | N/A | No out-of-band authentication; emailed links are verification and reset (V6.4) |
| V6.6.2 | 2 | Out-of-band authentication requests, codes, or tokens are bound to the original authentication … | N/A | As V6.6.1 |
| V6.6.3 | 2 | A code based out-of-band authentication mechanism is protected against brute force attacks … | N/A | As V6.6.1 |
| V6.8.1 | 2 | Verify that, if the application supports multiple identity providers (IdPs), the user's identity cannot … | N/A | No external identity providers |
| V6.8.2 | 2 | The presence and integrity of digital signatures on authentication assertions (for example … | N/A | As V6.8.1 |
| V6.8.3 | 2 | SAML assertions are uniquely processed and used only once within the validity … | N/A | As V6.8.1 |
| V6.8.4 | 2 | Verify that, if an application uses a separate Identity Provider (IdP) and expects specific … | N/A | As V6.8.1 |

### V7 Session Management

| ID | L | Requirement (abridged) | Status | Evidence |
|---|---|---|---|---|
| V7.1.1 | 2 | The user's session inactivity timeout and absolute maximum session lifetime are documented … | Fixed | Documented in [Sessions](#sessions) |
| V7.1.2 | 2 | The documentation defines how many concurrent (parallel) sessions are allowed for one … | Fixed | Documented in [Sessions](#sessions): no limit on parallel sessions |
| V7.1.3 | 2 | All systems that create and manage user sessions as part of a … | N/A | No federated identity |
| V7.2.1 | 1 | The application performs all session token verification using a trusted, backend service. | Pass | Server-side Django sessions in PostgreSQL |
| V7.2.2 | 1 | The application uses either self-contained or reference tokens that are dynamically generated … | Pass | A new session key per sign-in. Legacy edit links are V1 capabilities, not sessions, and go with task 9.6 |
| V7.2.3 | 1 | If reference tokens are used to represent user sessions, they are unique … | Pass | 32 random characters from 36 (about 165 bits), from `secrets` |
| V7.2.4 | 1 | The application generates a new session token on user authentication, including re-authentication … | Pass | Django replaces the session key on sign-in |
| V7.3.1 | 2 | There is an inactivity timeout such that re-authentication is enforced according to … | Accepted | No inactivity timeout, by decision ([Sessions](#sessions)) |
| V7.3.2 | 2 | There is an absolute maximum session lifetime such that re-authentication is enforced … | Pass | Sessions end 14 days after sign-in or their last change (Django's default); requests alone don't extend them |
| V7.4.1 | 1 | When session termination is triggered (such as logout or expiration), the application … | Pass | Signing out deletes the server-side session |
| V7.4.2 | 1 | The application terminates all active sessions when a user account is disabled … | Pass | Deleting an account ([ADR-016](adr/ADR-016-account-deletion-grace-period.md)) or suspending it (task 9.0) ends every session (`sessions_revoked_at`) |
| V7.4.3 | 2 | The application gives the option to terminate all other active sessions after … | Pass | Changing or resetting the password ends every other session at once (sessions are bound to the password hash), without asking |
| V7.4.4 | 2 | All pages that require authentication have easy and visible access to logout … | Pass | **Sign out** in the account menu on every page |
| V7.4.5 | 2 | Application administrators are able to terminate active sessions for an individual user … | Pass | `suspend_account` ends one account's sessions; all sessions end by emptying `django_session` ([Sessions](#sessions)) |
| V7.5.1 | 2 | The application requires full re-authentication before allowing modifications to sensitive account attributes … | Pass | The email address can't be changed; a password change needs the current one |
| V7.5.2 | 2 | Users are able to view and (having authenticated again with at least … | Accepted | No list of active sessions to review; changing the password signs out every other device. Revisit with Q6 |
| V7.6.1 | 2 | Session lifetime and termination between Relying Parties (RPs) and Identity Providers (IdPs) … | N/A | No identity providers |
| V7.6.2 | 2 | Creation of a session requires either the user's consent or an explicit … | Pass | Sessions start only from an explicit sign-in or sign-up |

### V8 Authorization

| ID | L | Requirement (abridged) | Status | Evidence |
|---|---|---|---|---|
| V8.1.1 | 1 | Authorization documentation defines rules for restricting function-level and data-specific access based on … | Pass | [12](12-AUTHORIZATION.md) list and group matrices |
| V8.1.2 | 2 | Authorization documentation defines rules for field-level access restrictions (both read and write) … | Pass | [12](12-AUTHORIZATION.md): content, settings and tags fields; email addresses only to their own account |
| V8.2.1 | 1 | The application ensures that function-level access is restricted to consumers with explicit … | Pass | Every action goes through `sharing/policy.py` |
| V8.2.2 | 1 | The application ensures that data-specific access is restricted to consumers with explicit … | Pass | Lookups start from the visible queryset; nested ids are scoped to their parent (IDOR tests) |
| V8.2.3 | 2 | The application ensures that field-level access is restricted to consumers with explicit … | Pass | Field-level rules (settings by the owner, content by editors, tags), write serializers list their fields |
| V8.3.1 | 1 | The application enforces authorization rules at a trusted service layer and doesn't … | Pass | Decided on the server; the UI only mirrors `permissions` |
| V8.4.1 | 2 | Multi-tenant applications use cross-tenant controls to ensure consumer operations will never affect … | N/A | Not multi-tenant: every list and group has its own access rules (V8.2) |

### V9 Self-contained Tokens

All 7 L1/L2 requirements are N/A: No self-contained tokens (JWT) are used: sessions are server-side.

### V10 OAuth and OIDC

All 29 L1/L2 requirements are N/A: No OAuth or OpenID Connect: no social or external sign-in.

### V11 Cryptography

| ID | L | Requirement (abridged) | Status | Evidence |
|---|---|---|---|---|
| V11.1.1 | 2 | There is a documented policy for management of cryptographic keys and a … | Fixed | Keys and their lifecycle in [Cryptographic inventory](#cryptographic-inventory) |
| V11.1.2 | 2 | A cryptographic inventory is performed, maintained, regularly updated, and includes all cryptographic … | Fixed | [Cryptographic inventory](#cryptographic-inventory) |
| V11.2.1 | 2 | Industry-validated implementations (including libraries and hardware-accelerated implementations) are used for cryptographic operations. | Pass | Python's `hashlib`, `hmac` and `secrets`, Django, and OpenSSL in nginx |
| V11.2.2 | 2 | The application is designed with crypto agility such that random number, authenticated … | Pass | Django's `PASSWORD_HASHERS` upgrades hashes on sign-in; `SECRET_KEY_FALLBACKS` rotates the signing key; TLS settings live in nginx |
| V11.2.3 | 2 | All cryptographic primitives utilize a minimum of 128-bits of security based on … | Pass | SHA-256, PBKDF2-SHA256, HMAC-SHA256 with a 50-character random key; TLS with ECDHE and AES-GCM or ChaCha20 |
| V11.3.1 | 1 | Insecure block modes (e.g., ECB) and weak padding schemes (e.g., PKCS#1 v1.5) … | Pass | The application encrypts nothing itself; TLS uses AEAD suites only |
| V11.3.2 | 1 | Only approved ciphers and modes such as AES with GCM are used. | Pass | As V11.3.1 |
| V11.3.3 | 2 | Encrypted data is protected against unauthorized modification preferably by using an approved … | Pass | As V11.3.1 (AEAD) |
| V11.4.1 | 1 | Only approved hash functions are used for general cryptographic use cases, including … | Pass | SHA-256 for token hashes and media names, HMAC-SHA256 for Django's signatures; no MD5 or SHA-1 (MD5 hashes passwords only in the test suite, for speed) |
| V11.4.2 | 2 | Passwords are stored using an approved, computationally intensive, key derivation function (also … | Pass | PBKDF2-SHA256 with Django 5.2's 1,000,000 iterations |
| V11.4.3 | 2 | Hash functions used in digital signatures, as part of data authentication or … | Pass | SHA-256 |
| V11.4.4 | 2 | The application uses approved key derivation functions with key stretching parameters when … | N/A | No keys are derived from passwords |
| V11.5.1 | 2 | All random numbers and strings which are intended to be non-guessable must … | Accepted | Owner tokens have 256 bits and session keys about 165, but list, group and short codes have 96 bits: V1's format, which invariant 1 keeps. Guessing is online only, rate-limited, and a private list also needs membership |
| V11.6.1 | 2 | Only approved cryptographic algorithms and modes of operation are used for key … | N/A | No key generation or signatures beyond Django's HMAC |

### V12 Secure Communication

| ID | L | Requirement (abridged) | Status | Evidence |
|---|---|---|---|---|
| V12.1.1 | 1 | Only the latest recommended versions of the TLS protocol are enabled, such … | Pass | TLS 1.2 and 1.3 only (nginx) |
| V12.1.2 | 2 | Only recommended cipher suites are enabled, with the strongest cipher suites set … | Pass | Mozilla's intermediate suites: AEAD with forward secrecy |
| V12.1.3 | 2 | The application validates that mTLS client certificates are trusted before using the … | N/A | No client certificates |
| V12.2.1 | 1 | TLS is used for all connectivity between a client and external facing … | Pass | HTTPS only: pages redirect, API and account requests are refused over HTTP |
| V12.2.2 | 1 | External facing services use publicly trusted TLS certificates. | Pass | Let's Encrypt certificates (deployment notes in the README) |
| V12.3.1 | 2 | An encrypted protocol such as TLS is used for all inbound and … | Accepted | nginx → api and api → PostgreSQL stay on the host's private compose network, unencrypted. SMTP uses STARTTLS by default; the fetcher validates TLS. Revisit if services leave the single host |
| V12.3.2 | 2 | TLS clients validate certificates received before communicating with a TLS server. | Pass | The fetcher validates certificates for the original host name; Django's SMTP STARTTLS uses a validating default context |
| V12.3.3 | 2 | TLS or another appropriate transport encryption mechanism used for all connectivity between … | Accepted | As V12.3.1 |
| V12.3.4 | 2 | TLS connections between internal services use trusted certificates. Where internally generated or … | N/A | No internal TLS |

### V13 Configuration

| ID | L | Requirement (abridged) | Status | Evidence |
|---|---|---|---|---|
| V13.1.1 | 2 | All communication needs for the application are documented. This must include external … | Pass | [14](14-INFRASTRUCTURE.md) services and worker egress; [13](13-SECURITY.md#ssrf-safe-fetcher): outbound traffic is the mail relay (api) and user URLs (worker, public addresses only) |
| V13.2.1 | 2 | Communications between backend application components that don't support the application's standard user … | Pass | PostgreSQL with a password; no other backend services |
| V13.2.2 | 2 | Communications between backend application components, including local or operating system services, APIs … | Accepted | The containers run as non-root users, but the app connects as the database owner the postgres image creates (a superuser). A least-privilege role is recommended in the deployment guide (task 9.4) |
| V13.2.3 | 2 | If a credential has to be used for service authentication, the credential … | Pass | No default credentials: compose refuses to start without `POSTGRES_PASSWORD` and `DJANGO_SECRET_KEY` |
| V13.2.4 | 2 | An allowlist is used to define the external resources or systems with … | Accepted | The worker reaches the public internet with private and metadata ranges denied ([13](13-SECURITY.md#ssrf-safe-fetcher)): fetching any public page is the feature. The api makes no outbound HTTP calls |
| V13.2.5 | 2 | The web or application server is configured with an allowlist of resources … | Accepted | As V13.2.4 |
| V13.3.1 | 2 | A secrets management solution, such as a key vault, is used to … | Accepted | Secrets live in the host's `.env` and reach containers as environment variables; no vault on a single host |
| V13.3.2 | 2 | Access to secret assets adheres to the principle of least privilege. | Accepted | Only the deploying user should read `.env` (`chmod 600`, deployment guide in task 9.4) |
| V13.4.1 | 1 | The application is deployed either without any source control metadata, including the … | Pass | Images are built from `backend/` and `frontend/`, which hold no `.git` |
| V13.4.2 | 2 | Debug modes are disabled for all components in production environments to prevent … | Pass | `DEBUG` is off and `check --deploy --fail-level WARNING` runs in CI; Vite's dev server and `/design` aren't in production |
| V13.4.3 | 2 | Web servers do not expose directory listings to clients unless explicitly intended. | Pass | No directory listings (smoke test: media directories answer 403) |
| V13.4.4 | 2 | Using the HTTP TRACE method is not supported in production environments, to … | Pass | TRACE answers 405 (new smoke check) |
| V13.4.5 | 2 | Documentation (such as for internal APIs) and monitoring endpoints are not exposed … | Pass | `/api/docs/` and `/api/schema/` are public on purpose (public API); `/healthz` says only ok or unavailable; no admin or debug pages |

### V14 Data Protection

| ID | L | Requirement (abridged) | Status | Evidence |
|---|---|---|---|---|
| V14.1.1 | 2 | All sensitive data created and processed by the application has been identified … | Fixed | [Data classification](#data-classification) |
| V14.1.2 | 2 | All sensitive data protection levels have a documented set of protection requirements … | Fixed | [Data classification](#data-classification) |
| V14.2.1 | 1 | Sensitive data is only sent to the server in the HTTP message … | Accepted | Tokens and keys travel in headers or URL fragments, never in paths or queries. List and short codes are capabilities in URLs by design, protected by `no-referrer` and `noindex` |
| V14.2.2 | 2 | The application prevents sensitive data from being cached in server components, such … | Pass | nginx doesn't cache proxied answers; the database cache holds only rate-limit counters |
| V14.2.3 | 2 | Defined sensitive data is not sent to untrusted parties (e.g., user trackers) … | Pass | No trackers or third-party requests: the CSP allows only this origin, media is served locally, and the API docs are self-hosted (new) |
| V14.2.4 | 2 | Controls around sensitive data related to encryption, integrity verification, retention, how the … | Pass | [13](13-SECURITY.md): logging, media, retention through expiry and account deletion |
| V14.3.1 | 1 | Authenticated data is cleared from client storage, such as the browser DOM … | Fixed | Lists kept in memory for quick revisits are now dropped when the user signs out or changes (`onUserChange` in `useSession`). Legacy edit links stay on the device by design until task 9.6 |
| V14.3.2 | 2 | The application sets sufficient anti-caching HTTP response header fields (i.e., Cache-Control: no-store) … | Fixed | `Cache-Control: no-store` on API, account and short-URL answers (`config.middleware.no_store`) |
| V14.3.3 | 2 | Data stored in browser storage (such as localStorage, sessionStorage, IndexedDB, or cookies) … | Accepted | `localStorage` holds legacy lists' edit-link tokens (bearer credentials like a session token, V1's design) and preferences; removed with task 9.6 |

### V15 Secure Coding and Architecture

| ID | L | Requirement (abridged) | Status | Evidence |
|---|---|---|---|---|
| V15.1.1 | 1 | Application documentation defines risk based remediation time frames for 3rd party component … | Fixed | [Dependencies](#dependencies) |
| V15.1.2 | 2 | An inventory catalog, such as software bill of materials (SBOM), is maintained … | Pass | The inventory is `uv.lock` and the `package-lock.json` files: exact versions with hashes from PyPI and npm, kept current by Dependabot |
| V15.1.3 | 2 | The application documentation identifies functionality which is time-consuming or resource-demanding. This must … | Pass | [13](13-SECURITY.md#rate-limits) and [14](14-INFRASTRUCTURE.md): image decoding, page fetching, directory search and restore, each rate-limited |
| V15.2.1 | 1 | The application only contains components which have not breached the documented update … | Pass | No known vulnerabilities (2026-10-30), now checked by CI |
| V15.2.2 | 2 | The application has implemented defenses against loss of availability due to functionality … | Pass | Rate limits, request size limits, the worker's 120 s time limit, fetch limits, database statement timeouts |
| V15.2.3 | 2 | The production environment only includes functionality that is required for the application … | Pass | The production build has no `/design`; `DEBUG` is off; the test-only switches are off by default (`LEGACY_LIST_CREATION=off`, `FETCH_TEST_HOSTS` empty, allauth's limits on unless `AUTH_RATE_LIMITS=off`) |
| V15.3.1 | 1 | The application only returns the required subset of fields from a data … | Pass | Serializers list their fields; email addresses go only to their own account |
| V15.3.2 | 2 | Where the application backend makes calls to external URLs, it is configured … | Pass | The fetcher follows at most 3 redirects itself, checking each; there are no other backend calls |
| V15.3.3 | 2 | The application has countermeasures to protect against mass assignment attacks by limiting … | Pass | Write serializers accept only their fields (V1's mass-assignment test) |
| V15.3.4 | 2 | All proxying and middleware components transfer the user's original IP address correctly … | Pass | nginx overwrites `X-Forwarded-For`; DRF and allauth trust exactly one proxy |
| V15.3.5 | 2 | The application explicitly ensures that variables are of the correct type and … | Pass | Typed serializers and strict TypeScript |
| V15.3.6 | 2 | JavaScript code is written in a way that prevents prototype pollution, for … | Pass | No untrusted objects are merged into others; responses are read as typed data |
| V15.3.7 | 2 | The application has defenses against HTTP parameter pollution attacks, particularly if the … | Pass | DRF reads query strings and bodies separately, one value per parameter |

### V16 Security Logging and Error Handling

| ID | L | Requirement (abridged) | Status | Evidence |
|---|---|---|---|---|
| V16.1.1 | 2 | An inventory exists documenting the logging performed at each layer of the … | Fixed | [Logging](#logging) |
| V16.2.1 | 2 | Each log entry includes necessary metadata (such as when, where, who, what) … | Fixed | Every record has its time, level, logger, request id and user id; nginx's access log has the same request id |
| V16.2.2 | 2 | Time sources for all logging components are synchronized, and that timestamps in … | Pass | JSON logs use UTC; containers run in UTC; the host keeps time with NTP |
| V16.2.3 | 2 | The application only stores or broadcasts logs to the files and services … | Pass | Standard output only, kept by Docker's json-file driver, now rotated (`compose.prod.yaml`) |
| V16.2.4 | 2 | Logs can be read and correlated by the log processor that is … | Fixed | One JSON object per line in production (`config/logging.py`) |
| V16.2.5 | 2 | When logging sensitive data, the application enforces logging based on the data's … | Pass | No secrets or email addresses in logs, tested end to end (`tests/test_logging.py`) |
| V16.3.1 | 2 | All authentication operations are logged, including successful and unsuccessful attempts. Additional metadata … | Fixed | Sign-ins, failures, sign-outs, sign-ups, verifications and password changes and resets (`apps/accounts/signals.py`) |
| V16.3.2 | 2 | Failed authorization attempts are logged. For L3, this must include logging all … | Pass | Django logs every 4xx and 5xx (`django.request`), now with the request and user ids |
| V16.3.3 | 2 | The application logs the security events that are defined in the documentation … | Pass | Refused requests (400, 403, 429) are logged; moderation and operator actions are logged |
| V16.3.4 | 2 | The application logs unexpected errors and security control failures such as backend … | Pass | Unhandled errors with tracebacks; fetch and mail failures |
| V16.4.1 | 2 | All logging components appropriately encode data to prevent log injection. | Fixed | The JSON formatter escapes control characters; request ids from outside are validated |
| V16.4.2 | 2 | Logs are protected from unauthorized access and cannot be modified. | Pass | Container logs are readable by root and the docker group only |
| V16.4.3 | 2 | Logs are securely transmitted to a logically separate system for analysis, detection … | Accepted | Logs aren't shipped to a separate system yet; the deployment guide (task 9.4) recommends a log driver or collector |
| V16.5.1 | 2 | A generic message is returned to the consumer when an unexpected or … | Pass | `DEBUG` off; errors are generic bodies with a `code` (`config/exceptions.py`) |
| V16.5.2 | 2 | The application continues to operate securely when external resource access fails, for … | Pass | A failed fetch falls back to the host name and letter icon; a failed mail relay fails that request only (a report answers 503) |
| V16.5.3 | 2 | The application fails gracefully and securely, including when an exception occurs, preventing … | Pass | Atomic services; the policy denies unless a rule allows |

### V17 WebRTC

All 7 L1/L2 requirements are N/A: No WebRTC.
