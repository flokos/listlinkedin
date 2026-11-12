# ADR-021: The extension has its own GitHub Releases; Mozilla signs the Firefox build

- Status: Accepted (2026-11-11, user: D37). Follows D36 (no store publishing for now).
  Since extension `1.0.1` the Firefox add-on updates itself
  ([ADR-023](ADR-023-extension-self-updates.md)): the first consequence below is replaced.
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

1. **The extension is released on its own**, apart from the site (user, 2026-11-11): a tag
   `extension-v<version>` on `main` and a GitHub Release of that name. Pushing the tag runs
   the workflow `extension-release.yml`, which checks that the tag names the version in
   `extension/package.json` and is on `main`, builds the extension for production's address
   in the same Docker targets as CI, and publishes the release with a zip per browser.
2. **An extension release is never GitHub's "latest" release.** The server deploys the
   latest release and only `vX.Y.Z` tags ([ADR-018](ADR-018-pull-based-deployment.md)); the
   workflow creates its release with `--latest=false`, so the site's deployment never sees it.
3. **The same workflow has Mozilla sign the Firefox build as an unlisted add-on** and adds
   the signed `.xpi`, when the repository secrets `AMO_JWT_ISSUER` and `AMO_JWT_SECRET`
   exist. Without them it warns and the release has no signed file. The readable source
   (`git archive` of `extension/`) is sent along, because the build is bundled.
4. **The site points to one extension version.** Its "Browser extension" page (`/extension`)
   links to the files of the release `extension-v<EXTENSION_VERSION>`
   (`frontend/src/utils/extensionDownloads.ts`); CI checks that this is the version in
   `extension/package.json`. The page hosts nothing itself and loads nothing from GitHub:
   they are plain links.
5. **The extension has its own version** (`extension/package.json`, `1.0.0` first), raised
   whenever a new one is released.
6. The tool is Mozilla's `web-ext`, a locked dev dependency of `extension/`, run in the
   extension's Docker image. No third-party action handles the credentials.

## Consequences

- Firefox users get a file that stays installed. There are still no automatic updates: a new
  version is a new download (no `update_url`; that needs a hosted update manifest, later if
  wanted).
- Two secrets exist that the application never sees. They live only in GitHub's secret store
  and reach one workflow step as environment variables. Whoever holds them can submit
  versions of this add-on ID; they are revoked on addons.mozilla.org.
- The extension's code and source are sent to Mozilla at each of its releases. That
  is the same code as in this repository.
- The add-on ID belongs to the Mozilla account that signs it first. Listing it on
  addons.mozilla.org later uses the same account and ID.
- Releasing the extension deploys nothing, and releasing the site doesn't release the
  extension. The order matters once: the extension's release must exist before the site that
  links to it is released, and an extension that needs new endpoints works only once the
  site has them.
- A new extension version reaches the site's page with the next site release, because the
  version is a constant in the frontend. Looking it up from GitHub at run time would make
  every visitor's browser call GitHub, which the site promises not to do.
- If someone marks an extension release as "latest" by hand, the server's deploy job ignores
  it and fails until a site release is latest again.
- If the workflow fails it can be run again for the tag. Re-signing a version Mozilla
  already signed fails: raise the version.

## Not decided here

Publishing in the Chrome Web Store or listing on addons.mozilla.org (D36: later, on the
owner's decision), and automatic updates.
