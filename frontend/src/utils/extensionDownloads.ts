// Where the browser extension's builds are: the files of its own GitHub Release
// (`extension-v<version>`, made by .github/workflows/extension-release.yml; docs/extension.md).
// They are built for https://listlinkedin.versioncontrol.xyz: someone running their own site
// builds their own (extension/README.md) and changes these.

/**
 * The extension version this site offers. CI checks that it is extension/package.json's, so
 * raising one without the other fails; that release must exist before the site is released.
 * public/extension-updates.json names the same version (a test checks it): releasing the site
 * is what makes installed Firefox add-ons update to it.
 */
export const EXTENSION_VERSION = '1.0.1'

const REPOSITORY = 'https://github.com/flokos/listlinkedin'
const TAG = `extension-v${EXTENSION_VERSION}`
const FILES = `${REPOSITORY}/releases/download/${TAG}`

export const extensionDownloads = {
  /** Chrome, Edge and other Chromium browsers: a zip to unpack and load. */
  chrome: `${FILES}/listlinkedin-${EXTENSION_VERSION}-chrome.zip`,
  /** Firefox: the add-on signed by Mozilla, which Firefox keeps installed. */
  firefox: `${FILES}/listlinkedin-${EXTENSION_VERSION}-firefox-signed.xpi`,
  /** The release's own page, with every file. */
  release: `${REPOSITORY}/releases/tag/${TAG}`,
  /** The whole guide: permissions, updating, what to do when something is wrong. */
  guide: `${REPOSITORY}/blob/main/docs/extension.md`,
} as const
