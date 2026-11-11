# ADR-021: The extension is handed out with GitHub Releases; Mozilla signs the Firefox build

- Status: Accepted (2026-11-11, user: D37). Follows D36 (no store publishing for now).
- Related: [docs/extension.md](../../extension.md),
  [ADR-018](ADR-018-pull-based-deployment.md) (what a release does to the server),
  [13 Logging and secrets](../13-SECURITY.md#logging-and-secrets),
  [17 phase 11](../17-IMPLEMENTATION-ROADMAP.md#phase-11-browser-extension)

## Context

The extension (phase 11) is not published in a store (D36): people install a build by hand.
Chrome and Edge keep an unpacked folder. Release Firefox does not: it installs for good only
what Mozilla has signed, and loads anything else as a temporary add-on that is gone when it
closes. The owner tried exactly that and asked for a build Firefox keeps (2026-11-11).

Mozilla signs add-ons that are not listed on addons.mozilla.org ("unlisted", self-distributed)
through its API, for free, after an automatic check. It needs API credentials of a Mozilla
account, and it signs each version of an add-on once.

## Decision

1. **A GitHub Release carries the extension.** The workflow `extension-release.yml` runs when
   a release is published (and by hand for a tag), builds the extension from that tag for
   production's address in the same Docker targets as CI, and attaches a zip per browser.
2. **The same workflow has Mozilla sign the Firefox build as an unlisted add-on** and
   attaches the signed `.xpi`, when the repository secrets `AMO_JWT_ISSUER` and
   `AMO_JWT_SECRET` exist. Without them it skips the step and says so. The readable source
   (`git archive` of `extension/`) is sent along, because the build is bundled.
3. **The extension has its own version** (`extension/package.json`, `1.0.0` first), raised
   in every release that changes `extension/`.
4. The tool is Mozilla's `web-ext`, a locked dev dependency of `extension/`, run in the
   extension's Docker image. No third-party action handles the credentials.

## Consequences

- Firefox users get a file that stays installed. There are still no automatic updates: a new
  version is a new download (no `update_url`; that needs a hosted update manifest, later if
  wanted).
- Two secrets exist that the application never sees. They live only in GitHub's secret store
  and reach one workflow step as environment variables. Whoever holds them can submit
  versions of this add-on ID; they are revoked on addons.mozilla.org.
- The extension's code and source are sent to Mozilla at each release that changes it. That
  is the same code as in this repository.
- The add-on ID belongs to the Mozilla account that signs it first. Listing it on
  addons.mozilla.org later uses the same account and ID.
- The workflow only adds files to a release. If it fails, the deployment (ADR-018) is not
  affected, and it can be run again for the tag. Re-signing a version Mozilla already signed
  fails: raise the version.

## Not decided here

Publishing in the Chrome Web Store or listing on addons.mozilla.org (D36: later, on the
owner's decision), and automatic updates.
