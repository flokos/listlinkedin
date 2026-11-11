// The listlinkedin site an extension build talks to. It is fixed when the extension is built
// (LL_BASE_URL): a browser grants an extension its sites at install, from the manifest.

export interface Site {
  /** `https://lists.example.org`: where the API and the Connect page are. */
  origin: string
  /** The match pattern for that site, for host permissions and the content script. */
  pattern: string
}

export function siteFrom(value: string): Site {
  let url: URL
  try {
    url = new URL(value)
  } catch {
    throw new Error(`LL_BASE_URL isn't a URL: ${value}`)
  }
  const local = url.hostname === 'localhost' || url.hostname === '127.0.0.1'
  if (url.protocol !== 'https:' && !(url.protocol === 'http:' && local))
    throw new Error('LL_BASE_URL must be https (plain http is for localhost only).')
  if (url.pathname !== '/' || url.search || url.hash || url.username || url.password)
    throw new Error('LL_BASE_URL must be a site address only: no path, query or credentials.')
  // Match patterns have no port: the pattern covers the host on every port.
  return { origin: url.origin, pattern: `${url.protocol}//${url.hostname}/*` }
}
