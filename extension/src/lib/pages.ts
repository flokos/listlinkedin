// The page to save, and whether the site will take it.
import { onSite } from './config'
import { ext } from './ext'

export interface PageToSave {
  url: string
  title: string
}

const MAX_URL_BYTES = 2048
const MAX_TITLE = 255

/**
 * Why the site won't take `url`, or null when it will. The rules are the server's
 * (backend/apps/sharing/domain.py): http and https only, no credentials, not the site itself.
 * The server stays the judge; this spares a request and says it plainly.
 */
export function whyNotSaveable(url: string | undefined): string | null {
  let parsed: URL
  try {
    parsed = new URL(url ?? '')
  } catch {
    return 'This page has no address that can be saved.'
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:')
    return "Only web pages (http and https) can be saved, and this isn't one."
  if (parsed.username || parsed.password)
    return "Addresses with a username or password in them can't be saved."
  if (onSite(parsed.href)) return "Pages of listlinkedin itself can't be saved to a list."
  if (new TextEncoder().encode(parsed.href).length > MAX_URL_BYTES)
    return "This page's address is too long to save."
  return null
}

/** A tab's title as a link title: one line, at most what the site stores. */
export const titleFrom = (title: string | undefined): string =>
  (title ?? '').replace(/\s+/g, ' ').trim().slice(0, MAX_TITLE)

/**
 * The page the popup is about: the active tab (the popup's own permission, activeTab, shows
 * its address and title). Opened as a page instead, with `?url=…&title=…`, it is about that
 * address: how a right-click on a link asks to choose a list.
 */
export async function pageToSave(search = window.location.search): Promise<PageToSave | null> {
  const params = new URLSearchParams(search)
  const url = params.get('url')
  if (url) return { url, title: titleFrom(params.get('title') ?? '') }
  const [tab] = await ext().tabs.query({ active: true, currentWindow: true })
  if (!tab?.url) return null
  return { url: tab.url, title: titleFrom(tab.title) }
}

/** What to call this browser on the site: "Firefox on Linux". A label, nothing depends on it. */
export function browserName(userAgent = navigator.userAgent): string {
  const browser = /Firefox\//.test(userAgent)
    ? 'Firefox'
    : /Edg\//.test(userAgent)
      ? 'Edge'
      : /OPR\//.test(userAgent)
        ? 'Opera'
        : /Chrome\//.test(userAgent)
          ? 'Chrome'
          : 'Browser'
  const system = /Windows/.test(userAgent)
    ? 'Windows'
    : /Android/.test(userAgent)
      ? 'Android'
      : /Mac OS X|Macintosh/.test(userAgent)
        ? 'macOS'
        : /CrOS/.test(userAgent)
          ? 'ChromeOS'
          : /Linux/.test(userAgent)
            ? 'Linux'
            : ''
  return system ? `${browser} on ${system}` : browser
}
