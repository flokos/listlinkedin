// The private edit link: /l/{code}/manage#t={token}. The token lives in the URL fragment,
// which browsers never send to servers, so it stays out of request logs and Referer headers
// (W3C TAG, "Good Practices for Capability URLs").

const FRAGMENT_KEY = 't'

export function buildEditLink(code: string, token: string, origin = window.location.origin) {
  return `${origin}/l/${encodeURIComponent(code)}/manage#${FRAGMENT_KEY}=${encodeURIComponent(token)}`
}

/** The token from a `#t=…` fragment, or null. */
export function tokenFromHash(hash: string): string | null {
  const params = new URLSearchParams(hash.replace(/^#/, ''))
  const token = params.get(FRAGMENT_KEY)?.trim()
  return token ? token : null
}

/**
 * Accepts what a user might paste to regain edit access: a full edit link, or a bare token.
 * Returns the token and, when present in the link, the list code.
 */
export function parseEditInput(input: string): { token: string; code?: string } | null {
  const text = input.trim()
  if (!text) return null
  try {
    const url = new URL(text)
    const token = tokenFromHash(url.hash)
    if (!token) return null
    const match = url.pathname.match(/^\/l\/([^/]+)\/manage\/?$/)
    return { token, code: match ? decodeURIComponent(match[1]!) : undefined }
  } catch {
    // Not a URL: treat as a raw token (URL-safe Base64, as the API issues).
    return /^[A-Za-z0-9_-]{20,}$/.test(text) ? { token: text } : null
  }
}
