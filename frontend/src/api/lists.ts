// Lists and links on /api/v2/ (docs/v2/09-API-DESIGN.md). Shapes follow
// backend/apps/sharing/v2/serializers.py.
import { request, type WriteOptions } from './client'

export interface SharedLink {
  id: string
  title: string | null
  destination_url: string
  short_url: string | null
  created_at: string
  updated_at: string
  /** 0-based order among the list's links. */
  position?: number
  description?: string | null
  /** the uploaded icon (same-origin /media/ URL), if any. */
  icon_url?: string | null
  /** what to show, with the server's precedence applied (user > fetched >
   * fallback). Clients don't re-derive it. */
  display?: LinkDisplay
  /** the link this one was copied from. */
  source_link_id?: string | null
  /** fetching the page's details (title, description, icon). */
  metadata_status?: MetadataStatus
  /** what the page itself says, once fetched. Offered as suggestions; never
   * copied into the link's own fields. */
  fetched?: LinkFetched | null
}

/** `pending`: being fetched; `unavailable`: couldn't be; `disabled`: fetching is off. */
export type MetadataStatus = 'pending' | 'ready' | 'unavailable' | 'disabled'

export interface LinkFetched {
  title: string | null
  description: string | null
  icon_url: string | null
  site_name: string | null
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
  /** What someone may add to a report (docs/v2/09-API-DESIGN.md#moderation). */
  reportDetailsLength: 1000,
} as const

const enc = encodeURIComponent
// Lists with accounts and visibility. The session decides who you are; `permissions` tells
// the UI what this user may do.

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
  /** Lowercase words and hyphens, at most 10. Editors and owners change them. */
  tags: string[]
  owner: { display_name: string } | null
  /** Always false since v2.1.0, when lists from before accounts were retired. */
  legacy: boolean
  created_at: string
  updated_at: string
  expires_at: string | null
  /** The latest revision's number; the list's ETag is `"r{head_revision}"`. */
  head_revision: number
  link_count: number
  my_role: ListRole | null
  permissions: string[]
  /** Null for an ordinary list. For a copy, the list it was copied from: `parent` is null
   * when you can't open that list (or it is gone). */
  origin: ListOrigin | null
}

export interface ListOrigin {
  kind: 'fork'
  parent: { code: string; title: string } | null
}

export interface ListInput {
  title?: string
  description?: string
  visibility?: Visibility
  allow_fork?: boolean
  allow_branch?: boolean
  tags?: string[]
  expires_at?: string | null
}

const v2 = (path: string) => `/api/v2${path}`

export const myLists = (signal?: AbortSignal) =>
  request<Page<ListDetail>>(v2('/lists/?page_size=100'), { signal })

/** How many lists the signed-in user owns (all pages). */
export const ownedListCount = () =>
  request<Page<ListDetail>>(v2('/lists/?role=owner&page_size=1')).then((page) => page.count)

/** "Make a copy": a new private list you own with this list's content. Retrying with the
 * same key returns the first copy. */
export const forkList = (code: string, input: { title?: string }, idempotencyKey: string) =>
  request<ListDetail>(v2(`/lists/${code}/fork/`), {
    method: 'POST',
    body: input,
    headers: { 'Idempotency-Key': idempotencyKey },
  })

export const createAccountList = (input: ListInput, idempotencyKey: string) =>
  request<ListDetail>(v2('/lists/'), {
    method: 'POST',
    body: input,
    headers: { 'Idempotency-Key': idempotencyKey },
  })

export const getListDetail = (code: string, signal?: AbortSignal) =>
  request<ListDetail>(v2(`/lists/${enc(code)}/`), { signal })

// Content writes take WriteOptions: the If-Match precondition and the new ETag (task 3.4).
export const changeList = (code: string, changes: ListInput, opts?: WriteOptions) =>
  request<ListDetail>(v2(`/lists/${enc(code)}/`), { method: 'PATCH', body: changes, ...opts })

export const removeList = (code: string) =>
  request<null>(v2(`/lists/${enc(code)}/`), { method: 'DELETE' })

// A list holds at most 100 links, so one page of 100 is the whole list.
export const listLinks = (code: string, signal?: AbortSignal, onEtag?: WriteOptions['onEtag']) =>
  request<Page<SharedLink>>(v2(`/lists/${enc(code)}/links/?page_size=${LIMITS.linksPerList}`), {
    signal,
    onEtag,
  })

export const createLink = (code: string, link: LinkInput, opts?: WriteOptions) =>
  request<SharedLink>(v2(`/lists/${enc(code)}/links/`), { method: 'POST', body: link, ...opts })

export const changeLink = (code: string, id: string, link: LinkInput, opts?: WriteOptions) =>
  request<SharedLink>(v2(`/lists/${enc(code)}/links/${enc(id)}/`), {
    method: 'PATCH',
    body: link,
    ...opts,
  })

export const removeLink = (code: string, id: string, opts?: WriteOptions) =>
  request<null>(v2(`/lists/${enc(code)}/links/${enc(id)}/`), { method: 'DELETE', ...opts })

// Reports to the operator (docs/v2/09-API-DESIGN.md#moderation), for lists and groups.

/** `phishing` covers malware too. */
export type ReportReason = 'phishing' | 'spam' | 'illegal' | 'other'

export interface ReportInput {
  reason: ReportReason
  /** At most 1000 characters. */
  details?: string
}

/** Tells the operator about a list (anyone who can view it, except its owner). Answers 202;
 * 429 when sent too often, 503 when the report couldn't be sent. */
export const reportList = (code: string, input: ReportInput) =>
  request<null>(v2(`/lists/${enc(code)}/report/`), { method: 'POST', body: input })

/** Sets the list's image (PNG, JPEG, WebP or GIF ≤2 MB; re-encoded to fit 512×512). An
 * account's right (owner or editor). Not versioned. */
export function uploadListImage(code: string, file: File) {
  const body = new FormData()
  body.append('file', file)
  return request<ListDetail>(v2(`/lists/${enc(code)}/image/`), { method: 'PUT', body })
}

export const removeListImage = (code: string) =>
  request<null>(v2(`/lists/${enc(code)}/image/`), { method: 'DELETE' })

/** Fetch the page's details again (editors; at most once an hour per link, else 429). */
export const refreshLinkMetadata = (code: string, id: string) =>
  request<void>(v2(`/lists/${code}/links/${id}/refresh-metadata/`), { method: 'POST' })

/** Sets a link's own icon (PNG, JPEG, WebP or GIF ≤2 MB; the server re-encodes it). */
export function uploadLinkIcon(code: string, id: string, file: File, opts?: WriteOptions) {
  const body = new FormData()
  body.append('file', file)
  return request<SharedLink>(v2(`/lists/${enc(code)}/links/${enc(id)}/icon/`), {
    method: 'PUT',
    body,
    ...opts,
  })
}

export const removeLinkIcon = (code: string, id: string, opts?: WriteOptions) =>
  request<null>(v2(`/lists/${enc(code)}/links/${enc(id)}/icon/`), { method: 'DELETE', ...opts })

/** Moves one link to `toIndex` (0-based, clamped) and returns the links in their new order. */
// Moves need no precondition: they apply to the current order. They still report the ETag.
export const reorderLinks = (
  code: string,
  linkId: string,
  toIndex: number,
  onEtag?: WriteOptions['onEtag'],
) =>
  request<SharedLink[]>(v2(`/lists/${enc(code)}/reorder/`), {
    method: 'POST',
    body: { link: linkId, to_index: toIndex },
    onEtag,
  })

/** Moves a link to the end of another list you can edit; returns the new link there. */
export const moveLinkToList = (
  code: string,
  id: string,
  targetCode: string,
  onEtag?: WriteOptions['onEtag'],
) =>
  request<SharedLink>(v2(`/lists/${enc(code)}/links/${enc(id)}/move-to-list/`), {
    method: 'POST',
    body: { list: targetCode },
    onEtag,
  })

// History (docs/v2/09-API-DESIGN.md#revisions-and-restore).

export type RevisionKind = 'created' | 'edited' | 'restored' | 'migrated' | 'forked'

export interface RevisionSummary {
  added: number
  removed: number
  modified: number
  moved: number
  /** The list fields that changed: "title", "description". */
  list: string[]
}

export interface Revision {
  number: number
  kind: RevisionKind
  created_at: string
  /** An account's name, "edit link" (an edit made with a V1 edit link, before v2.1.0), or null
   * for the baseline of a list from before V2. */
  author: { display_name: string } | 'edit link' | null
  summary: RevisionSummary
  restored_from: number | null
}

export interface SnapshotLink {
  id: string
  url: string
  title: string | null
  description: string | null
  icon: string | null
  position: number
}

export type LinkChangeKind = 'added' | 'removed' | 'modified' | 'moved'

export interface LinkChange {
  id: string
  url: string
  title: string | null
  changes: LinkChangeKind[]
  position_before: number | null
  position_after: number | null
  fields: Record<string, { before: string | null; after: string | null }>
}

export interface RevisionDetail extends Revision {
  snapshot: { list: { title: string; description: string }; links: SnapshotLink[] }
  diff_from_previous: {
    list: Record<string, { before: string; after: string }>
    links: LinkChange[]
  }
}

export const listRevisions = (code: string, page = 1) =>
  request<Page<Revision>>(v2(`/lists/${enc(code)}/revisions/?page=${page}`))

export const getRevision = (code: string, number: number) =>
  request<RevisionDetail>(v2(`/lists/${enc(code)}/revisions/${number}/`))

/** Makes the list's content what it was at `number`; `head` is the version you looked at. */
export const restoreRevision = (code: string, number: number, head: number) =>
  request<{ revision: number; changed: boolean }>(v2(`/lists/${enc(code)}/restore/`), {
    method: 'POST',
    body: { revision: number },
    ifMatch: head,
  })
