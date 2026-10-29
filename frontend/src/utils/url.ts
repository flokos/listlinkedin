// Client-side checks that mirror the server's link rules (backend/apps/sharing/domain.py),
// so most mistakes are caught before a request. The server remains the authority.
import { LIMITS } from '../api'
import { avatarTints } from '../design/tokens'

/** Adds `https://` when the user typed a bare host like `example.com/page`. */
export function withScheme(input: string): string {
  const text = input.trim()
  if (!text || /^[a-z][a-z0-9+.-]*:/i.test(text)) return text
  return `https://${text.replace(/^\/\//, '')}`
}

/** An error message for an invalid destination URL, or null when it looks acceptable. */
export function validateUrl(input: string): string | null {
  const text = input.trim()
  if (!text) return 'Enter a link.'
  let url: URL
  try {
    url = new URL(text)
  } catch {
    return "That doesn't look like a valid link."
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    return 'Only http and https links are allowed.'
  }
  if (url.username || url.password) return "Links can't contain a username or password."
  if (!url.hostname) return "That doesn't look like a valid link."
  if (new TextEncoder().encode(text).length > LIMITS.urlBytes) {
    return `Links can be at most ${LIMITS.urlBytes} characters long.`
  }
  if (url.host === window.location.host) return "Links can't point to this site."
  return null
}

/**
 * Hostname for display: lowercase and without `www.`. Internationalized hosts stay in
 * punycode (`xn--…`), as the server stores them: decoding would let look-alike hosts
 * (Cyrillic "а" for Latin "a") pass for familiar sites.
 */
export function displayHost(input: string): string {
  try {
    return new URL(input).hostname.replace(/^www\./, '')
  } catch {
    return input
  }
}

/** A compact "host/path" form of a URL for secondary text. */
export function displayUrl(input: string): string {
  try {
    const url = new URL(input)
    const path = `${url.pathname === '/' ? '' : url.pathname}${url.search}${url.hash}`
    return `${url.hostname.replace(/^www\./, '')}${path}`
  } catch {
    return input
  }
}

/**
 * A path on this site to continue to (e.g. `?next=` after signing in), or `fallback`.
 * Rejects anything that could leave the site: `//host`, `/\host`, other schemes, and
 * control characters, which browsers strip, turning `/\t/host` into `//host`.
 */
export function safeRedirectPath(value: unknown, fallback = '/'): string {
  if (typeof value !== 'string' || !value.startsWith('/')) return fallback
  const hasControl = [...value].some((char) => char.charCodeAt(0) < 0x20 || char === '\u007f')
  if (value.startsWith('//') || value.includes('\\') || hasControl) return fallback
  return value
}

/**
 * Reads `name` from the URL fragment (`#key=…`) and removes the whole fragment from the
 * address bar and history entry. Secrets such as reset keys travel in the fragment, which
 * browsers never send to servers, and shouldn't linger on screen afterwards.
 */
export function takeHashParam(name: string): string | null {
  const value = new URLSearchParams(window.location.hash.slice(1)).get(name)
  if (window.location.hash) {
    history.replaceState(history.state, '', window.location.pathname + window.location.search)
  }
  return value
}

export type AvatarTint = keyof typeof avatarTints
const AVATAR_TINTS = Object.keys(avatarTints) as AvatarTint[]

/** A stable tint and initial for a host, so the same site always looks the same. */
export function avatarFor(input: string): { initial: string; tint: AvatarTint } {
  const host = displayHost(input)
  let hash = 0
  for (const char of host) hash = (hash * 31 + char.charCodeAt(0)) >>> 0
  return {
    initial: (host.match(/[\p{L}\p{N}]/u)?.[0] ?? '?').toUpperCase(),
    tint: AVATAR_TINTS[hash % AVATAR_TINTS.length]!,
  }
}

/**
 * A list's code from a pasted link (`…/l/{code}/{slug}`, `…/g/{group}/l/{code}`) or the bare
 * code, or undefined. Only the shape is checked: the server says whether the list exists.
 */
export function listCodeFrom(input: string): string | undefined {
  const text = input.trim()
  const fromLink = text.match(/\/l\/([A-Za-z0-9_-]+)/)
  if (fromLink) return fromLink[1]
  return /^[A-Za-z0-9_-]{4,32}$/.test(text) ? text : undefined
}
