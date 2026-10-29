// Lists and links: the V1 API (/api/v1/). Shapes follow backend/apps/sharing/serializers.py.
import { request } from './client'

export interface SharedList {
  id: string
  public_code: string
  public_url: string
  title: string
  created_at: string
  expires_at: string | null
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
  /** /api/v2/ only: 0-based order among the list's links. */
  position?: number
  /** /api/v2/ only. */
  description?: string | null
  /** /api/v2/ only: the uploaded icon (same-origin /media/ URL), if any. */
  icon_url?: string | null
  /** /api/v2/ only: what to show, with the server's precedence applied (user > fetched >
   * fallback). Clients don't re-derive it. */
  display?: LinkDisplay
  /** /api/v2/ only: the link this one was copied from. */
  source_link_id?: string | null
}

export interface LinkDisplay {
  title: string
  description: string | null
  icon_url: string | null
  /** The site's name if fetched, else the host. */
  site_name: string
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
  /** /api/v2/ only. */
  description?: string | null
}

/** The server's hard limits, mirrored for client-side hints (backend/apps/sharing/domain.py). */
export const LIMITS = {
  titleLength: 255,
  descriptionLength: 1000,
  linksPerList: 100,
  urlBytes: 2048,
  /** Uploaded images (docs/v2/09-API-DESIGN.md#uploads). */
  imageBytes: 2 * 1024 * 1024,
} as const

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

// /api/v2/: lists with accounts and visibility (docs/v2/09-API-DESIGN.md). A legacy list's
// owner token, when this browser has one, goes along as a bearer header; otherwise the
// session decides. `permissions` tells the UI what this user may do.

export type Visibility = 'private' | 'unlisted' | 'public'
export type ListRole = 'owner' | 'editor' | 'viewer'

export interface ListDetail {
  id: string
  code: string
  slug: string
  url: string
  title: string
  description: string
  /** The list's image (same-origin /media/ URL), if any. */
  image_url: string | null
  visibility: Visibility
  allow_fork: boolean
  allow_branch: boolean
  owner: { display_name: string } | null
  /** A V1 list managed by its edit link until someone adds it to their account. */
  legacy: boolean
  created_at: string
  updated_at: string
  expires_at: string | null
  link_count: number
  my_role: ListRole | null
  permissions: string[]
}

export interface ListInput {
  title?: string
  description?: string
  visibility?: Visibility
  allow_fork?: boolean
  allow_branch?: boolean
  expires_at?: string | null
}

const v2 = (path: string) => `/api/v2${path}`

export const myLists = (signal?: AbortSignal) =>
  request<Page<ListDetail>>(v2('/lists/?page_size=100'), { signal })

/** How many lists the signed-in user owns (all pages). */
export const ownedListCount = () =>
  request<Page<ListDetail>>(v2('/lists/?role=owner&page_size=1')).then((page) => page.count)

export const createAccountList = (input: ListInput, idempotencyKey: string) =>
  request<ListDetail>(v2('/lists/'), {
    method: 'POST',
    body: input,
    headers: { 'Idempotency-Key': idempotencyKey },
  })

export const getListDetail = (code: string, token?: string, signal?: AbortSignal) =>
  request<ListDetail>(v2(`/lists/${enc(code)}/`), { token, signal })

export const changeList = (code: string, changes: ListInput, token?: string) =>
  request<ListDetail>(v2(`/lists/${enc(code)}/`), { method: 'PATCH', body: changes, token })

export const removeList = (code: string, token?: string) =>
  request<null>(v2(`/lists/${enc(code)}/`), { method: 'DELETE', token })

export const replaceToken = (code: string, token: string) =>
  request<{ owner_token: string }>(v2(`/lists/${enc(code)}/rotate-token/`), {
    method: 'POST',
    token,
  })

/** Adds a legacy list to the signed-in account; its edit link stops working. */
export const claimList = (code: string, token: string) =>
  request<ListDetail>(v2(`/lists/${enc(code)}/claim/`), { method: 'POST', token })

export const listLinks = (code: string, token?: string, signal?: AbortSignal) =>
  request<Page<SharedLink>>(v2(`/lists/${enc(code)}/links/?page_size=${LIMITS.linksPerList}`), {
    token,
    signal,
  })

export const createLink = (code: string, link: LinkInput, token?: string) =>
  request<SharedLink>(v2(`/lists/${enc(code)}/links/`), { method: 'POST', body: link, token })

export const changeLink = (code: string, id: string, link: LinkInput, token?: string) =>
  request<SharedLink>(v2(`/lists/${enc(code)}/links/${enc(id)}/`), {
    method: 'PATCH',
    body: link,
    token,
  })

export const removeLink = (code: string, id: string, token?: string) =>
  request<null>(v2(`/lists/${enc(code)}/links/${enc(id)}/`), { method: 'DELETE', token })

/** Sets a link's own icon (PNG, JPEG, WebP or GIF ≤2 MB; the server re-encodes it). */
export function uploadLinkIcon(code: string, id: string, file: File) {
  const body = new FormData()
  body.append('file', file)
  return request<SharedLink>(v2(`/lists/${enc(code)}/links/${enc(id)}/icon/`), {
    method: 'PUT',
    body,
  })
}

export const removeLinkIcon = (code: string, id: string) =>
  request<null>(v2(`/lists/${enc(code)}/links/${enc(id)}/icon/`), { method: 'DELETE' })

/** Moves one link to `toIndex` (0-based, clamped) and returns the links in their new order. */
export const reorderLinks = (code: string, linkId: string, toIndex: number, token?: string) =>
  request<SharedLink[]>(v2(`/lists/${enc(code)}/reorder/`), {
    method: 'POST',
    body: { link: linkId, to_index: toIndex },
    token,
  })

/** Moves a link to the end of another list you can edit; returns the new link there. */
export const moveLinkToList = (code: string, id: string, targetCode: string) =>
  request<SharedLink>(v2(`/lists/${enc(code)}/links/${enc(id)}/move-to-list/`), {
    method: 'POST',
    body: { list: targetCode },
  })
