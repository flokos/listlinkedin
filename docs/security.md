# Security notes

## Controls in place

* **Identifiers**: list and redirect codes come from `secrets.token_bytes(12)` (96 bits),
  are Base64URL-encoded, and are unique at the database level. Nothing is sequential.
* **Owner token**: `secrets.token_urlsafe(32)` (256 bits). Only its SHA-256 digest is
  stored. It is compared with `hmac.compare_digest`. It appears only in the creation
  response and in the owner-only rotation response, and never in URLs, logs, error
  messages or schema examples.
* **Token rotation and revocation**: `POST /api/v1/lists/{code}/rotate-token/` (owner only)
  issues a new token and revokes the old one immediately. Deleting a list also revokes its
  token.
* **List-scoped authorization**: every write loads the list from its public code and
  checks the token against that list's stored hash. A link id from another list is a `404`.
* **No mass assignment**: serializers allow writing only `title` (list) and `title` /
  `destination_url` (link). The backend sets ids, codes, hashes and timestamps.
* **URL validation**: http/https only, no embedded credentials, well-formed, at most 2048
  characters.
* **Destination host policy**: links to this service are refused, which prevents redirect
  loops and chains that hide the real destination behind our own `/r/`. "This service"
  means every name it answers to: the `PUBLIC_BASE_URL` host and all `ALLOWED_HOSTS`
  entries, subdomains included, so aliases like `127.0.0.1` are covered too. Names outside
  `ALLOWED_HOSTS` can't loop because Django answers them with `400`. Operators can
  denylist hosts with `BLOCKED_DESTINATION_HOSTS`; an invalid entry stops the app at
  startup instead of breaking redirects at runtime. Hosts are compared in punycode form,
  using the same IDNA2008/UTS #46 rules as browsers, so `bücher.example` and
  `xn--bcher-kva.example` match either way and `faß.example` is never confused with
  `fass.example`. The denylist is checked
  again on every redirect, so blocking a phishing domain also disables short URLs that are
  already shared (`410`). Storing hosts in punycode also makes look-alike Unicode domains
  visible as `xn--…`.
* **Redirects**: always `302`, `Cache-Control: no-store` (so a changed destination is
  never served stale), `Referrer-Policy: no-referrer`. Destinations are validated as
  http(s) before storage, and Django's `HttpResponseRedirect` additionally refuses schemes
  such as `javascript:` and `data:`. `/l/{code}` only ever redirects to this API's own path.
* **Size limits**: request bodies with a `Content-Length` over 16 KB are rejected with
  `413`. Chunked bodies without a length are read as empty by Django's WSGI handler, so
  they can't get around the limit. Lists hold at most 100 links.
* **Rate limits**: list creation and owner writes are throttled per client IP, including
  failed token attempts (throttling runs before the ownership check). Public reads are not
  throttled. Counters live in a PostgreSQL cache table, so they're shared by every Gunicorn
  worker and instance and survive restarts. The table holds up to 100,000 entries, so live
  counters are never evicted early. Django's default of 300 would reset limits once more
  than 300 clients were active. Each check holds a per-client Postgres advisory lock, so
  concurrent bursts can't exceed a limit: 200 parallel requests at 30/hour let exactly 30
  through, against 50 without the lock. The client IP is the socket address unless
  `DJANGO_NUM_PROXIES` says how many trusted proxies to read from `X-Forwarded-For`.
* **Authorization re-checked under the lock**: every owner write re-reads the list with a
  row lock and rejects the request (`403`) if the token was rotated after it was checked,
  so a stolen token can't finish a write that was in flight during rotation.
* **Secrets in logs**: the app logs list ids only. Django's error reporter masks
  `HTTP_AUTHORIZATION`. Gunicorn's access log records the request line and never the
  `Authorization` header.
* **Capability URLs**: every response sends `Referrer-Policy: no-referrer` and
  `X-Robots-Tag: noindex, nofollow`, so list and short URLs don't leak through the
  `Referer` header and aren't indexed if someone posts them publicly.
* **No SSRF surface**: the server never fetches destination URLs, so there are no previews
  and no reachability checks. `/healthz` reveals only whether the database is reachable.
* **Production**: HTTPS redirect, HSTS, proxy SSL header, secure cookies, `DEBUG=False`,
  secrets only from the environment, non-root container user. Database
  `lock_timeout`/`statement_timeout` keep a stuck lock from tying up workers.
* **TLS proxy (bundled nginx)**: it is the only published service, so the API port can't
  be reached directly to skip HTTPS or forge `X-Forwarded-*` headers. nginx:
  - overwrites `X-Forwarded-For` with the address it actually received, so clients can't
    inject hops,
  - drops unknown `Host` headers and refuses TLS handshakes for unknown names,
  - buffers and caps request bodies (32 KB),
  - times out slow headers and bodies after 10 s, which protects Gunicorn's sync workers,
  - hides its version and allows TLS 1.2 and 1.3 only (Mozilla intermediate profile).

  `deploy/smoke-test.sh` checks these properties against the real stack in CI. A mutation
  run confirmed it fails when the proxy appends to `X-Forwarded-For` instead of overwriting
  it.
* **Client IPs on rootless Docker**: rootless Docker's default port driver hides client
  IPs behind its gateway address, which would merge every client into one rate limit. Run
  production on rootful Docker, or use the `slirp4netns` port driver.

## Known limitations and risks

* **Rate limits are per IP.** Many users behind one NAT, e.g. a whole office, share a single
  limit. Each throttled write costs a few small database queries. That's negligible at this
  scale, and proxy-level limiting can take over if traffic ever needs it. Redis would add
  speed, not correctness.
* **Client IP depends on proxy configuration.** In production the client IP comes from
  `X-Forwarded-For` using `DJANGO_NUM_PROXIES`. If the setting doesn't match the real
  number of proxies, clients can spoof their IP and dodge rate limits. Only deployment
  configuration can fix this, not code.
* **Phishing and abusive redirects (reduced, not solved).** Anyone can still create a list
  pointing anywhere, and the owner can change a destination after sharing. The denylist is
  reactive and manual. There's no automated reputation check (e.g. the Google Safe Browsing
  Lookup API), moderation queue or abuse-report endpoint. Each would add an external
  dependency or new surface, so add them only before a public, internet-facing launch, or
  keep the service internal.
* **Bearer-token theft.** Whoever holds the owner token controls the list, and an attacker
  holding it can rotate it first and lock the owner out. Keep tokens out of chats, tickets
  and screenshots, and only send them over HTTPS.
* **Public codes are capabilities.** Anyone with a list URL can read it. `no-referrer` and
  `noindex` reduce accidental leaks, but URLs still leak through browser history, chat
  previews and server logs, so don't put confidential links in a list.
* **No token recovery**, by design.
