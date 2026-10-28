// Typed client for the Django API (/api/v1/). Shapes follow backend/apps/sharing/serializers.py.
// Same origin in every environment (Vite proxy in development, nginx in production).

export interface SharedList {
  id: string
  public_code: string
  public_url: string
  title: string
  created_at: string
  expires_at: string
}

export interface CreatedList extends SharedList {
  /** Private. Returned only once, on creation (and on rotation). */
  owner_token: string
}

export interface SharedLink {
  id: string
  title: string | null
  destination_url: string
  short_url: string | null
  created_at: string
  updated_at: string
}

export interface Page<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface LinkInput {
  title?: string | null
  destination_url?: string
}

/** The server's hard limits, mirrored for client-side hints (backend/apps/sharing/domain.py). */
export const LIMITS = { titleLength: 255, linksPerList: 100, urlBytes: 2048 } as const

export class ApiError extends Error {
  /** DRF field errors, e.g. `{destination_url: ["…"]}`; `non_field_errors` included. */
  readonly fieldErrors: Record<string, string[]>
  /** DRF's `detail` message, when the body carries one. */
  readonly detail: string | undefined
  /** Seconds to wait before retrying (429), from the Retry-After header. */
  readonly retryAfter: number | undefined

  constructor(
    readonly status: number,
    readonly body: unknown,
    retryAfter?: string | null,
  ) {
    super(`API request failed with status ${status}`)
    this.name = 'ApiError'
    this.fieldErrors = {}
    this.detail = undefined
    if (body && typeof body === 'object' && !Array.isArray(body)) {
      for (const [key, value] of Object.entries(body)) {
        if (key === 'detail' && typeof value === 'string') this.detail = value
        else if (Array.isArray(value)) this.fieldErrors[key] = value.map(String)
        else if (typeof value === 'string') this.fieldErrors[key] = [value]
      }
    }
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

interface RequestOptions {
  method?: string
  body?: unknown
  token?: string
  signal?: AbortSignal
}

async function request<T>(
  path: string,
  { method = 'GET', body, token, signal }: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(`/api/v1${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
      credentials: 'omit', // bearer tokens only; the API never uses cookies
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new NetworkError(error)
  }

  const data: unknown = response.status === 204 ? null : await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(response.status, data, response.headers.get('Retry-After'))
  return data as T
}

const enc = encodeURIComponent

// Lists
export const createList = (title: string) =>
  request<CreatedList>('/lists/', { method: 'POST', body: { title } })

export const getList = (code: string, signal?: AbortSignal) =>
  request<SharedList>(`/lists/${enc(code)}/`, { signal })

export const updateList = (code: string, token: string, title: string) =>
  request<SharedList>(`/lists/${enc(code)}/`, { method: 'PATCH', body: { title }, token })

export const deleteList = (code: string, token: string) =>
  request<null>(`/lists/${enc(code)}/`, { method: 'DELETE', token })

export const rotateToken = (code: string, token: string) =>
  request<{ owner_token: string }>(`/lists/${enc(code)}/rotate-token/`, { method: 'POST', token })

// Links. A list holds at most 100 links, so one page of 100 is the whole list.
export const getLinks = (code: string, signal?: AbortSignal) =>
  request<Page<SharedLink>>(`/lists/${enc(code)}/links/?page_size=${LIMITS.linksPerList}`, {
    signal,
  })

export const addLink = (code: string, token: string, link: LinkInput) =>
  request<SharedLink>(`/lists/${enc(code)}/links/`, { method: 'POST', body: link, token })

export const updateLink = (code: string, token: string, id: string, link: LinkInput) =>
  request<SharedLink>(`/lists/${enc(code)}/links/${enc(id)}/`, {
    method: 'PATCH',
    body: link,
    token,
  })

export const deleteLink = (code: string, token: string, id: string) =>
  request<null>(`/lists/${enc(code)}/links/${enc(id)}/`, { method: 'DELETE', token })

/**
 * Checks that `token` owns the list: a PATCH with an empty body changes no content for the
 * owner and is a 401/403 for anyone else. It does bump the list's `updated_at`, which is
 * invisible in the UI; the API has no read-only owner check (docs/decisions.md).
 */
export const verifyOwnership = (code: string, token: string) =>
  request<SharedList>(`/lists/${enc(code)}/`, { method: 'PATCH', body: {}, token })
