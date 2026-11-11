// The extension's access to the site. The manifest asks for it at install, and both browsers
// grant it then, but a user can take it away later (and Firefox before version 127 didn't
// grant it at install). Without it the browser blocks every request to the site, so the
// pages check and ask again.
import { SITE } from './config'
import { ext } from './ext'

/** The site as a match pattern: the host on any port, as in the manifest. */
export function sitePattern(): string {
  const url = new URL(SITE)
  return `${url.protocol}//${url.hostname}/*`
}

export const hasSiteAccess = (): Promise<boolean> =>
  ext().permissions.contains({ origins: [sitePattern()] })

/** Asks the user for it. Browsers only allow this from a click. */
export const requestSiteAccess = (): Promise<boolean> =>
  ext().permissions.request({ origins: [sitePattern()] })
