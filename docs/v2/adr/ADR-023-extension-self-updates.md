# ADR-023: The Firefox add-on updates itself from a file on the site

- Status: Accepted (2026-11-12, user: D40). Extends
  [ADR-021](ADR-021-extension-distribution.md), whose "no automatic updates" consequence it
  replaces for Firefox.
- Related: [docs/extension.md](../../extension.md),
  [ADR-018](ADR-018-pull-based-deployment.md),
  [13 Logging and secrets](../13-SECURITY.md#logging-and-secrets)

## Context

The Firefox add-on is signed by Mozilla as an unlisted add-on and installed from a file
(ADR-021). An unlisted add-on gets no updates from Mozilla: every new version was a new
download. The owner considered listing it on addons.mozilla.org, which brings updates but
also a review of every version, public listing texts and a reviewer's view of the name
(a prepared change, PR #84, was closed unmerged), and chose to stay unlisted and to update
the add-on ourselves (2026-11-12).

Firefox supports this for add-ons that Mozilla doesn't host: the manifest names an
`update_url`, an https address of a JSON file listing versions and where to get them.
Firefox reads it about once a day and installs a newer version by itself. It installs only a
file that Mozilla signed for the same add-on ID. Mozilla refuses `update_url` in listed
add-ons, so this and a listing exclude each other.

## Decision

1. **The Firefox manifest names `update_url`: `<site>/extension-updates.json`**, on the site
   the build talks to (`extension/scripts/manifest.ts`). A build for a local http site has
   none.
2. **The file is part of the site**: `frontend/public/extension-updates.json`, served by
   nginx as a static file. It lists one version, the one the "Browser extension" page
   offers, and links to the signed `.xpi` of that extension release on GitHub. A test keeps
   it equal to `EXTENSION_VERSION`, and the smoke test checks that the server answers with
   JSON.
3. **Releasing the site is what rolls an extension version out.** The order of ADR-021
   stays: the extension's tag first (Mozilla signs, the GitHub Release gets the file), then
   a site release, whose page and update file both name that version.
4. **Chrome is unchanged**: an unpacked extension can't update itself, and Chrome takes
   self-hosted updates only where an administrator's policy allows them.
5. The linter runs with `--self-hosted`, which is what the add-on is.

## Consequences

- From `1.0.1`, an installed Firefox add-on moves to each newer version within about a
  day of the site's release, and keeps its connection. `1.0.0` has no `update_url`: whoever
  installed it installs `1.0.1` by hand once.
- The update file and the download link are on two hosts: our site and GitHub. If either is
  down, nothing updates and nothing breaks.
- Whoever can change the site's files can point installed add-ons at another file. Firefox
  still installs it only if Mozilla signed it for this add-on's ID, so that needs the
  Mozilla keys as well (ADR-021). It can't install other code, and it can't downgrade below
  the installed version.
- A bad extension version reaches every Firefox user within a day of the site's release.
  The way back is a higher version with the fix, not removing the entry.
- Every installed copy asks the site for that file about daily: a plain request without
  cookies or the account's token. The server sees it like any visit (address, user agent).
- Listing on addons.mozilla.org later means removing `update_url`; Mozilla then updates.

## Not decided here

The Chrome Web Store; listing on addons.mozilla.org (D36: later, on the owner's decision).
