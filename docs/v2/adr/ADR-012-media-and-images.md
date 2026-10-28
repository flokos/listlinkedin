# ADR-012: Media: Pillow re-encoding, same-origin serving

- Status: Accepted (2026-10-28, V2 planning)
- Related: [13 Media](../13-SECURITY.md#media), [14](../14-INFRASTRUCTURE.md)

## Context

V2 shows 128×128 icons on tiles, list and group images, and icons and Open Graph images
fetched from third-party sites. V1 has no file storage, and its CSP allows images only from
`'self'` and `data:`. Uploaded and fetched images are untrusted bytes: polyglots, decompression
bombs, wrong types, EXIF location data.

## Decision

- Every image, uploaded or fetched, goes through one pipeline: content sniffing (PNG, JPEG,
  WebP, GIF, and ICO for fetched icons only; **never SVG**), a pixel limit (16 MP, bomb
  warnings treated as errors), `verify` and reload, EXIF orientation, resize into fixed bounds
  (128×128 for icons, 512×512 for images), and **re-encode to WebP** (strips metadata,
  destroys payloads).
- Files are stored content-addressed (`media/{kind}/{hh}/{sha256}.webp`) on a `media`
  volume. nginx serves them under `/media/` with `nosniff`, a `default-src 'none'; sandbox`
  CSP and immutable caching. Django never serves media.
- The app's CSP stays strict. Because images are same-origin, no third-party image hosts are
  allowed and viewers' IPs never leak to icon hosts.
- Unreferenced files are garbage-collected weekly (`cleanup_media`), taking revision snapshots
  into account.

## Alternatives considered

- **Hotlinking fetched icons (relax `img-src`):** leaks visitor IPs and referrers to third
  parties, brings mixed or unsafe content, and weakens the CSP.
- **Storing images in PostgreSQL:** bloats the database and backups, and is slower to serve.
- **Object storage (S3) now:** unnecessary on one host. `django-storages` can be adopted later
  behind the same settings.
- **Accepting SVG:** scriptable content. It would need a sanitizer or rasterizer (heavy).

## Consequences

- New dependency: Pillow (13.0 current [R24]). New volume plus backups.
- Upload endpoints need a larger per-route body limit (2 MB) in Django's middleware and nginx.
- Media URLs aren't access-controlled. Their content-hash names are unguessable without the
  image (an accepted risk, [13](../13-SECURITY.md#media)).
