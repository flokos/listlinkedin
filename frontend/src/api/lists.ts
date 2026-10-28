// Lists and links: the V1 API (/api/v1/). Shapes follow backend/apps/sharing/serializers.py.
import { request } from './client'

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

const enc = encodeURIComponent
const v1 = (path: string) => `/api/v1${path}`

// Lists
export const createList = (title: string) =>
  request<CreatedList>(v1('/lists/'), { method: 'POST', body: { title } })

export const getList = (code: string, signal?: AbortSignal) =>
  request<SharedList>(v1(`/lists/${enc(code)}/`), { signal })

export const updateList = (code: string, token: string, title: string) =>
  request<SharedList>(v1(`/lists/${enc(code)}/`), { method: 'PATCH', body: { title }, token })

export const deleteList = (code: string, token: string) =>
  request<null>(v1(`/lists/${enc(code)}/`), { method: 'DELETE', token })

export const rotateToken = (code: string, token: string) =>
  request<{ owner_token: string }>(v1(`/lists/${enc(code)}/rotate-token/`), {
    method: 'POST',
    token,
  })

// Links. A list holds at most 100 links, so one page of 100 is the whole list.
export const getLinks = (code: string, signal?: AbortSignal) =>
  request<Page<SharedLink>>(v1(`/lists/${enc(code)}/links/?page_size=${LIMITS.linksPerList}`), {
    signal,
  })

export const addLink = (code: string, token: string, link: LinkInput) =>
  request<SharedLink>(v1(`/lists/${enc(code)}/links/`), { method: 'POST', body: link, token })

export const updateLink = (code: string, token: string, id: string, link: LinkInput) =>
  request<SharedLink>(v1(`/lists/${enc(code)}/links/${enc(id)}/`), {
    method: 'PATCH',
    body: link,
    token,
  })

export const deleteLink = (code: string, token: string, id: string) =>
  request<null>(v1(`/lists/${enc(code)}/links/${enc(id)}/`), { method: 'DELETE', token })

/**
 * Checks that `token` owns the list: a PATCH with an empty body changes no content for the
 * owner and is a 401/403 for anyone else. It does bump the list's `updated_at`, which is
 * invisible in the UI; the API has no read-only owner check (docs/decisions.md).
 */
export const verifyOwnership = (code: string, token: string) =>
  request<SharedList>(v1(`/lists/${enc(code)}/`), { method: 'PATCH', body: {}, token })
