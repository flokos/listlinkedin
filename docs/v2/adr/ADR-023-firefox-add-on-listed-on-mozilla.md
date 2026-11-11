# ADR-023: The Firefox add-on is listed on addons.mozilla.org

- Status: Accepted (2026-11-12, user: D40). Supersedes point 3 of
  [ADR-021](ADR-021-extension-distribution.md) (unlisted signing) and, for Firefox, the "no
  store publishing" part of D36. The rest of ADR-021 stands.
- Related: [docs/extension.md](../../extension.md),
  [ADR-018](ADR-018-pull-based-deployment.md),
  [13 Logging and secrets](../13-SECURITY.md#logging-and-secrets)

## Context

Since `extension-v1.0.0` Mozilla signed the Firefox build as an **unlisted** add-on: a file
on our GitHub Release that Firefox keeps installed. It has no page on addons.mozilla.org, so
nobody finds it by searching there, and it does not update itself. The owner looked for it on
Mozilla's site and asked for it to be there (2026-11-12).

Mozilla takes a version of an add-on once, in one channel. `1.0.0` is unlisted and stays so.

## Decision

1. **From version `1.0.1` the Firefox build is submitted to addons.mozilla.org as a listed
   add-on**, by the same workflow (`extension-release.yml`), with the same Mozilla account,
   keys and add-on ID. Mozilla reviews it, publishes it on the add-on's page
   (`https://addons.mozilla.org/firefox/addon/listlinkedin/`) and signs it.
2. **The listing's texts are in the repository**: `extension/amo-metadata.json` (address
   name, summary, description, category, privacy policy, support address, license, notes for
   the reviewer). The workflow sends it with every version. Screenshots are added by hand in
   Mozilla's Developer Hub: `web-ext` can't send them.
3. **The workflow doesn't wait for the review.** It publishes the GitHub Release first
   (the Chrome zip and the unsigned Firefox zip), then submits to Mozilla and ends. A review
   takes minutes to days. The release carries no signed `.xpi` any more.
4. **The site's Firefox button links to the add-on's page on addons.mozilla.org.** Chrome's
   still links to the zip on the GitHub Release. Both are plain links: the site loads nothing
   from either.
5. **Firefox updates the add-on through Mozilla.** No `update_url` and no update manifest of
   ours.
6. The Chrome Web Store stays undecided (D36): Chrome's build is installed by hand.

## Consequences

- People find the add-on by searching addons.mozilla.org, install it with one button, and
  get new versions without doing anything.
- A Firefox release is public only after Mozilla's review, which we don't control. A
  reviewer can refuse a version or ask for changes; the answer comes to the Mozilla
  account's email address. The name contains "linkedin", another company's mark: a reviewer
  may object to it.
- Order of a release: the extension's tag first; the site, whose page names that version,
  after Mozilla has published the add-on's page (once, for `1.0.1`; later versions keep the
  same page).
- Our privacy text is now also published by Mozilla. It must stay true when the extension
  changes: `amo-metadata.json` changes in the same pull request as the behaviour.
- A copy installed from the `1.0.0` file has the same add-on ID. Firefox asks Mozilla for
  updates of it by that ID, so it should move to the listed version by itself; if it doesn't,
  installing from the add-on's page replaces it and keeps the connection.
- If the submission fails after the GitHub Release was published, the workflow can be run
  again for the tag; once Mozilla has the version, a new attempt needs a new version.
- The keys' reach is unchanged (ADR-021): whoever holds them can submit versions of this
  add-on, now to a public page.

## Not decided here

The Chrome Web Store; listing texts in other languages.
