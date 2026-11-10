// HTTP client for the site's API (docs/v2/09-API-DESIGN.md). The extension signs in with a
// connected browser's session token in X-Session-Token (docs/v2/adr/ADR-020) and never sends
// the site's cookies: `credentials: 'omit'` on every request. With cookies, whoever is signed
// in on the site would answer instead of the connected account, and writes would need CSRF.
//
// The browser lets the extension call the site without CORS because the manifest names the
// site in host_permissions.
import { SITE } from './config'

/** The server refused the request. `userMessage` is what to show. */
export class ApiError extends Error {
  /** Field errors, e.g. `{destination_url: ["This URL is already in the list."]}`. */
  readonly fieldErrors: Record<string, string[]>
  /** The body's general message (`detail`, or a bare list of messages). */
  readonly detail: string | undefined
  /** Stable machine code (`not_authenticated`, `invalid_code`, …). */
  readonly code: string | undefined
  /** Seconds to wait before trying again (429), from Retry-After. */
  readonly retryAfter: number | undefined

  constructor(
    readonly status: number,
    body: unknown,
    retryAfter?: string | null,
  ) {
    super(`The API answered ${status}`)
    this.name = 'ApiError'
    const fieldErrors: Record<string, string[]> = {}
    let detail: string | undefined
    let code: string | undefined
    if (Array.isArray(body)) detail = body.find((item) => typeof item === 'string')
    else if (body && typeof body === 'object') {
      for (const [key, value] of Object.entries(body)) {
        if (key === 'detail' && typeof value === 'string') detail = value
        else if (key === 'code' && typeof value === 'string') code = value
        else if (Array.isArray(value)) fieldErrors[key] = value.map(String)
        else if (typeof value === 'string') fieldErrors[key] = [value]
      }
    }
    this.fieldErrors = fieldErrors
    this.detail = detail
    this.code = code
    const seconds = retryAfter ? Number.parseInt(retryAfter, 10) : Number.NaN
    this.retryAfter = Number.isFinite(seconds) ? seconds : undefined
  }

  get userMessage(): string {
    if (this.status === 429) return waitMessage(this.retryAfter)
    if (this.detail) return this.detail
    const first = Object.values(this.fieldErrors)[0]?.[0]
    return first ?? describeStatus(this.status)
  }
}

/** The site couldn't be reached at all: offline, DNS, a refused connection. */
export class NetworkError extends Error {
  constructor(cause: unknown) {
    super("Couldn't reach listlinkedin. Check your connection and try again.", { cause })
    this.name = 'NetworkError'
  }
}

function waitMessage(seconds: number | undefined): string {
  if (seconds === undefined) return 'Too many requests. Wait a moment and try again.'
  const minutes = Math.ceil(seconds / 60)
  return minutes <= 1
    ? 'Too many requests. Try again in a minute.'
    : `Too many requests. Try again in ${minutes} minutes.`
}

function describeStatus(status: number): string {
  if (status === 403) return "You can't change this list."
  if (status === 404 || status === 410) return 'This list no longer exists.'
  if (status === 413) return 'That was too much to save at once.'
  return status >= 500
    ? 'Something went wrong at listlinkedin. Try again in a moment.'
    : 'Something went wrong. Try again.'
}

/** What to show for anything a request can throw. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.userMessage
  if (error instanceof NetworkError) return error.message
  return 'Something went wrong. Try again.'
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  /** Sent as JSON. */
  body?: unknown
  /** The connected browser's session token. */
  token?: string
  /** A UUID per user action: repeating the request returns the first result. */
  idempotencyKey?: string
  signal?: AbortSignal
}

/** Requests `path` (e.g. `/api/v2/lists/`) on the site and returns the parsed JSON body. */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, token, idempotencyKey, signal } = options
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers['X-Session-Token'] = token
  if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey

  let response: Response
  try {
    response = await fetch(`${SITE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
      credentials: 'omit',
      cache: 'no-store',
      referrerPolicy: 'no-referrer',
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new NetworkError(error)
  }
  const data: unknown = response.status === 204 ? null : await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(response.status, data, response.headers.get('Retry-After'))
  return data as T
}
