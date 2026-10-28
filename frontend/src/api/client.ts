// HTTP client for the Django API. Same origin in every environment (Vite proxy in
// development, nginx in production), so the session cookie is first-party.

export class ApiError extends Error {
  /** Field errors, e.g. `{destination_url: ["…"]}` (DRF) or allauth's `errors[].param`. */
  readonly fieldErrors: Record<string, string[]>
  /** The body's general message: DRF's `detail`, or an allauth error without a field. */
  readonly detail: string | undefined
  /** Stable machine code from /api/v2/ (`not_authenticated`, `stale_preview`, …). */
  readonly code: string | undefined
  /** Seconds to wait before retrying (429), from the Retry-After header. */
  readonly retryAfter: number | undefined

  constructor(
    readonly status: number,
    readonly body: unknown,
    retryAfter?: string | null,
  ) {
    super(`API request failed with status ${status}`)
    this.name = 'ApiError'
    const fieldErrors: Record<string, string[]> = {}
    let detail: string | undefined
    let code: string | undefined
    if (body && typeof body === 'object' && !Array.isArray(body)) {
      for (const [key, value] of Object.entries(body)) {
        if (key === 'detail' && typeof value === 'string') detail = value
        else if (key === 'code' && typeof value === 'string') code = value
        else if (key === 'errors' && Array.isArray(value)) {
          // allauth: {status, errors: [{message, code, param?}]}
          for (const item of value as { message?: unknown; code?: unknown; param?: unknown }[]) {
            const message = typeof item?.message === 'string' ? item.message : undefined
            if (!message) continue
            if (typeof item.param === 'string') (fieldErrors[item.param] ??= []).push(message)
            else detail ??= message
            if (typeof item.code === 'string') code ??= item.code
          }
        } else if (Array.isArray(value)) fieldErrors[key] = value.map(String)
        else if (typeof value === 'string') fieldErrors[key] = [value]
      }
    }
    this.fieldErrors = fieldErrors
    this.detail = detail
    this.code = code
    const seconds = retryAfter ? Number.parseInt(retryAfter, 10) : Number.NaN
    this.retryAfter = Number.isFinite(seconds) ? seconds : undefined
  }

  /** The most useful single message for a toast or banner. */
  get userMessage(): string {
    if (this.detail) return this.detail
    const first = Object.values(this.fieldErrors)[0]?.[0]
    return first ?? describeStatus(this.status)
  }
}

/** A message suitable for showing to the user, for any error the client can throw. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.userMessage
  if (error instanceof NetworkError) return error.message
  return 'Something went wrong. Please try again.'
}

/** Thrown for network failures (offline, DNS, connection reset), never for HTTP errors. */
export class NetworkError extends Error {
  constructor(cause: unknown) {
    super('Could not reach the server. Check your connection and try again.', { cause })
    this.name = 'NetworkError'
  }
}

export function describeStatus(status: number): string {
  switch (status) {
    case 401:
    case 403:
      return "You don't have permission to change this list. Your edit link may have been replaced."
    case 404:
      return "This list doesn't exist or was deleted."
    case 410:
      return 'This list has expired.'
    case 413:
      return 'That request was too large.'
    case 429:
      return 'Too many requests. Please wait a moment and try again.'
    default:
      return status >= 500
        ? 'Something went wrong on our side. Please try again.'
        : 'Something went wrong. Please try again.'
  }
}

export const CSRF_COOKIE = 'csrftoken'
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

/** Django's CSRF token from its cookie (readable by design; sent back as a header). */
export function csrfToken(): string | undefined {
  const prefix = `${CSRF_COOKIE}=`
  const cookie = document.cookie.split('; ').find((part) => part.startsWith(prefix))
  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : undefined
}

export interface RequestOptions {
  method?: string
  body?: unknown
  /** A V1 owner token, sent as a bearer header. Such requests need no CSRF token. */
  token?: string
  signal?: AbortSignal
  /** Extra headers, e.g. allauth's key headers. */
  headers?: Record<string, string>
}

/** Requests `path` (absolute, e.g. `/api/v1/lists/`) and returns the parsed JSON body. */
export async function request<T>(
  path: string,
  { method = 'GET', body, token, signal, headers: extra }: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json', ...extra }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`
  if (!SAFE_METHODS.has(method) && !token) {
    // Session-authenticated writes need Django's CSRF token. The first visit may not have
    // the cookie yet; the session endpoint sets it.
    if (!csrfToken()) await fetchOrThrow('/api/v2/session/', { credentials: 'same-origin' })
    const csrf = csrfToken()
    if (csrf) headers['X-CSRFToken'] = csrf
  }

  const response = await fetchOrThrow(path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
    credentials: 'same-origin', // the session cookie; never sent to other sites
  })

  const data: unknown = response.status === 204 ? null : await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(response.status, data, response.headers.get('Retry-After'))
  return data as T
}

async function fetchOrThrow(input: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init)
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new NetworkError(error)
  }
}
