// Groups: workspaces of lists, /api/v2/groups/ (docs/v2/09-API-DESIGN.md#groups). Session
// only: an edit link grants nothing on groups. A group shows each viewer only the lists they
// may see; hidden lists are left out entirely, also from `list_count`.
import { request } from './client'
import type { ListDetail, ListRole, Page, ReportInput, Visibility } from './lists'

export interface GroupDetail {
  id: string
  code: string
  slug: string
  /** The group's page, `/g/{code}/{slug}`. */
  url: string
  title: string
  description: string
  image_url: string | null
  visibility: Visibility
  tags: string[]
  /** Shown on public groups and to the group's members. */
  owner: { display_name: string } | null
  created_at: string
  updated_at: string
  /** The lists this group shows you. */
  list_count: number
  my_role: ListRole | null
  /** `view`, `edit`, `add_list`, `view_members`, `settings`, `members`, `delete`, `leave`,
   * `report`. */
  permissions: string[]
}

/** A list in a group, as you see that list. */
export interface GroupList extends ListDetail {
  /** False when you see it only through your own role on it: others in the group don't. */
  shown_to_all: boolean
}

export interface GroupInput {
  title?: string
  description?: string
  visibility?: Visibility
  tags?: string[]
}

/** A group holds at most this many lists (backend/apps/groups/services.py). */
export const MAX_LISTS_PER_GROUP = 100

const enc = encodeURIComponent
const groups = (path = '') => `/api/v2/groups/${path}`

export const myGroups = (signal?: AbortSignal) =>
  request<Page<GroupDetail>>(groups('?page_size=100'), { signal })

export const createGroup = (input: GroupInput) =>
  request<GroupDetail>(groups(), { method: 'POST', body: input })

export const getGroup = (code: string, signal?: AbortSignal) =>
  request<GroupDetail>(groups(`${enc(code)}/`), { signal })

export const changeGroup = (code: string, changes: GroupInput) =>
  request<GroupDetail>(groups(`${enc(code)}/`), { method: 'PATCH', body: changes })

export const removeGroup = (code: string) =>
  request<null>(groups(`${enc(code)}/`), { method: 'DELETE' })

export const groupLists = (code: string, signal?: AbortSignal) =>
  request<GroupList[]>(groups(`${enc(code)}/lists/`), { signal })

/** Adds a list at the end: one you own or edit, or a public one. */
export const addGroupList = (code: string, listCode: string) =>
  request<GroupList>(groups(`${enc(code)}/lists/`), { method: 'POST', body: { list: listCode } })

/** Takes a list out of the group; the list itself is untouched. */
export const removeGroupList = (code: string, listCode: string) =>
  request<null>(groups(`${enc(code)}/lists/${enc(listCode)}/`), { method: 'DELETE' })

/** Moves a list to `toIndex` among the lists you are shown; answers with the new order. */
export const reorderGroupLists = (code: string, listCode: string, toIndex: number) =>
  request<GroupList[]>(groups(`${enc(code)}/reorder/`), {
    method: 'POST',
    body: { list: listCode, to_index: toIndex },
  })

/** Sets the group's image (PNG, JPEG, WebP or GIF ≤2 MB; the server re-encodes it). */
export function uploadGroupImage(code: string, file: File) {
  const body = new FormData()
  body.append('file', file)
  return request<GroupDetail>(groups(`${enc(code)}/image/`), { method: 'PUT', body })
}

export const removeGroupImage = (code: string) =>
  request<null>(groups(`${enc(code)}/image/`), { method: 'DELETE' })

/** Tells the operator about a group (anyone who can view it, except its owner). */
export const reportGroup = (code: string, input: ReportInput) =>
  request<null>(groups(`${enc(code)}/report/`), { method: 'POST', body: input })
