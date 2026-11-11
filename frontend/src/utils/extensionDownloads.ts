// Where the browser extension's builds are: files of the newest GitHub Release, under names
// that stay the same from release to release (.github/workflows/extension-release.yml,
// docs/extension.md). They are built for https://listlinkedin.versioncontrol.xyz: someone
// running their own site builds their own (extension/README.md) and changes these.
const RELEASE = 'https://github.com/flokos/listlinkedin/releases/latest'

export const extensionDownloads = {
  /** Chrome, Edge and other Chromium browsers: a zip to unpack and load. */
  chrome: `${RELEASE}/download/listlinkedin-chrome.zip`,
  /** Firefox: the add-on signed by Mozilla, which Firefox keeps installed. */
  firefox: `${RELEASE}/download/listlinkedin-firefox.xpi`,
  /** The release's own page, with every file and its version. */
  release: RELEASE,
  /** The whole guide: permissions, updating, what to do when something is wrong. */
  guide: 'https://github.com/flokos/listlinkedin/blob/main/docs/extension.md',
} as const
