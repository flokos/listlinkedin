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

/** Hostname for display: lowercase, without `www.`, and decoded from punycode by the URL parser where possible. */
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
