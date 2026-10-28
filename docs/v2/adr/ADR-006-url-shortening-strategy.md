# ADR-006: URL shortening: keep V1 codes, no polymorphic ShortURL, no external targets

- Status: Accepted (2026-10-28, V2 planning)
- Related: [04](../04-DOMAIN-MODEL.md#shortredirect-shortenershortredirect), [12 Short URLs](../12-AUTHORIZATION.md#short-urls-and-other-entry-points), [01 Identifiers](../01-V1-AUDIT.md#identifiers)

## Context

V1 already has a secure shortener. Codes are 16 Base64URL characters from
`secrets.token_bytes(12)` (96 bits), protected by DB unique constraints with savepoint retries
keyed on the violated constraint's name. List codes are a column (`public_code`, `/l/`). Link
codes live in `ShortRedirect` (`/r/`), whose destination follows the link's current URL. The
prompt proposes a `ShortURL` entity with targets LIST, GROUP, LINK and EXTERNAL_URL, asks for a
comparison of identifier strategies, and wants simple relational integrity rather than
unconstrained generic references.

## Decision

- **Identifier generation stays as in V1.** Cryptographically random 96-bit codes, DB
  uniqueness, bounded collision retries (`create_with_unique_code`).
- **No polymorphic `ShortURL` table.** Lists keep `public_code` (`/l/{code}`). Groups get a
  `code` column (`/g/{code}`). Links keep `ShortRedirect` (`/r/{code}`). Each has a real
  foreign key or is a column of its target, so there are no generic references.
- **Resolution re-checks state and visibility** on every request: tombstoned links → 404,
  private targets → 404 for unauthorized users, expired → 410, blocked host → 410.
- **EXTERNAL_URL targets are deferred.** A shortener for arbitrary URLs is an open-redirect
  and phishing tool with no V2 product need.
- Codes never change. Deleting a link tombstones it and keeps its redirect row, so a revival
  restores the same short URL.

## Alternatives considered

| Strategy | Verdict |
|---|---|
| Random Base62/Base64URL codes + uniqueness + retry (**V1**) | Kept: unpredictable, simple, safe under concurrency, constant-time lookup by unique index |
| UUID-derived codes | 22+ characters with no security gain over 96 random bits |
| Obfuscated UUIDs / encrypted ids | Added key management and complexity for what random codes already give (the prompt warns against it) |
| Sequential ids with reversible encoding (Hashids-style) | Enumerable and predictable. Rejected |
| Hash of the destination | The code would change when the URL changes, which breaks invariant S1, and truncated hashes collide |
| Generic `ShortURL(target_type, target_id)` | No FK integrity, and every resolution needs type dispatch. It only pays off for EXTERNAL_URL, which is deferred |

## Consequences

- Every V1 short URL keeps working with no migration.
- Adding external targets later means a new table with abuse controls and an ADR.
- A collision is astronomically unlikely (96 bits). Codes are unique per kind, and there is
  no cross-kind uniqueness requirement because the namespaces are separate (`/l/`, `/g/`,
  `/r/`).
