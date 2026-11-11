// Where the browser extension is: for Firefox on addons.mozilla.org, for Chrome the zip of its
// own GitHub Release (`extension-v<version>`, made by .github/workflows/extension-release.yml,
// which also submits the Firefox build to Mozilla; docs/extension.md, ADR-023).
// Both are built for https://listlinkedin.versioncontrol.xyz: someone running their own site
// builds their own (extension/README.md) and changes these.

/**
 * The extension version this site offers. CI checks that it is extension/package.json's, so
 * raising one without the other fails; that release must exist, and Mozilla must have
 * published the add-on's page, before the site is released.
 */
export const EXTENSION_VERSION = '1.0.1'

const REPOSITORY = 'https://github.com/flokos/listlinkedin'
const TAG = `extension-v${EXTENSION_VERSION}`
const FILES = `${REPOSITORY}/releases/download/${TAG}`

export const extensionDownloads = {
  /** Chrome, Edge and other Chromium browsers: a zip to unpack and load. */
  chrome: `${FILES}/listlinkedin-${EXTENSION_VERSION}-chrome.zip`,
  /** Firefox: the add-on's page on addons.mozilla.org, which installs and updates it. */
  firefox: 'https://addons.mozilla.org/firefox/addon/listlinkedin/',
  /** The release's own page, with every file. */
  release: `${REPOSITORY}/releases/tag/${TAG}`,
  /** The whole guide: permissions, updating, what to do when something is wrong. */
  guide: `${REPOSITORY}/blob/main/docs/extension.md`,
} as const
