// The listlinkedin site this build talks to. It is fixed at build time (LL_BASE_URL): the
// manifest grants the extension that one site and no other.

/** The site's origin, e.g. `https://lists.example.org`. */
export const SITE: string = __LL_BASE_URL__
export const VERSION: string = __LL_VERSION__

/** An address on the site, for opening in a tab. */
export const siteUrl = (path: string): string => `${SITE}${path}`

/** Whether `url` is a page of the site itself. */
export function onSite(url: string | undefined): boolean {
  try {
    return url !== undefined && new URL(url).origin === SITE
  } catch {
    return false
  }
}
