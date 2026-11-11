// The account's lists and groups: reading them, saving a page into a list, and sharing.
import { asAccount } from './account'
import { ApiError } from './api'
import {
  cacheLists,
  getCachedLists,
  getRecent,
  type ListSummary,
  markUsed,
  saveNewListVisibility,
  type Visibility,
} from './storage'

/** A list as /api/v2/ represents it (backend/apps/sharing/v2/serializers.py), as far as used. */
export interface ApiList {
  code: string
  title: string
  url: string
  visibility: Visibility
  link_count: number
  /** What this account may do, from the server's policy: never re-derived here. */
  permissions: string[]
}

export interface ApiGroup {
  code: string
  title: string
  url: string
  visibility: Visibility
  list_count: number
  permissions: string[]
}

interface ApiLink {
  id: string
  destination_url: string
  short_url: string | null
  display: { title: string; site_name: string }
}

interface Page<T> {
  next: string | null
  results: T[]
}

export interface GroupSummary {
  code: string
  title: string
  /** Its page on the site. */
  url: string
  visibility: Visibility
  /** The lists the group shows this account. */
  listCount: number
  /** The server's policy says this account may add lists to it. */
  canAddList: boolean
  /** The server's policy says this account may choose who can open the group. */
  canSet: boolean
  /** …may rename it, put its lists in another order and take lists out of it. */
  canEdit: boolean
  /** …may delete it. */
  canDelete: boolean
}

/** A link of a list, as much as showing and sharing it needs. */
export interface LinkSummary {
  id: string
  /** What the site shows for it: the user's title, else the page's, else the host. */
  title: string
  url: string
  site: string
  /** Opens the page through the site, for whoever may open the list. */
  shortUrl: string | null
}

/** The most links a list holds (backend/apps/sharing/domain.py). */
export const LINKS_PER_LIST = 100
const PAGE_SIZE = 100
const MAX_PAGES = 5

export const summary = (list: ApiList): ListSummary => ({
  code: list.code,
  title: list.title,
  url: list.url,
  visibility: list.visibility,
  linkCount: list.link_count,
  canEdit: list.permissions.includes('edit'),
  canSet: list.permissions.includes('settings'),
})

async function everyPage<T>(path: string): Promise<T[]> {
  const items: T[] = []
  for (let page = 1; page <= MAX_PAGES; page += 1) {
    const data = await asAccount<Page<T>>(`${path}?page_size=${PAGE_SIZE}&page=${page}`)
    items.push(...data.results)
    if (!data.next) break
  }
  return items
}

/** The lists the account owns or is a member of, most recently changed first. */
export async function fetchLists(): Promise<ListSummary[]> {
  const lists = (await everyPage<ApiList>('/api/v2/lists/')).map(summary)
  await cacheLists(lists)
  return lists
}

/** The lists as last seen, so the popup can show them before the site answers. */
export const cachedLists = getCachedLists

/** Puts a list as the site just sent it into what is kept, in its place (or first). */
async function remember(list: ListSummary): Promise<void> {
  const cached = (await getCachedLists()) ?? []
  const known = cached.some((other) => other.code === list.code)
  await cacheLists(
    known ? cached.map((other) => (other.code === list.code ? list : other)) : [list, ...cached],
  )
}

/** `lists` with the ones saved to last first, newest first; the rest keep their order. */
export function byLastUse(lists: ListSummary[], recent: string[]): ListSummary[] {
  const place = (list: ListSummary) => {
    const index = recent.indexOf(list.code)
    return index === -1 ? recent.length : index
  }
  return [...lists].sort((a, b) => place(a) - place(b))
}

/**
 * The list saved to last, as last seen, or null when nothing was saved from this browser yet
 * (or that list is gone). What a shortcut acts on: it never guesses another list.
 */
export async function lastUsedList(): Promise<ListSummary | null> {
  const [code] = await getRecent()
  const lists = (await getCachedLists()) ?? []
  return lists.find((list) => list.code === code) ?? null
}

export async function fetchGroups(): Promise<GroupSummary[]> {
  const groups = await everyPage<ApiGroup>('/api/v2/groups/')
  return groups.map(groupSummary)
}

/** A group as the popup keeps it. What the account may do is the server's word. */
export const groupSummary = (group: ApiGroup): GroupSummary => ({
  code: group.code,
  title: group.title,
  url: group.url,
  visibility: group.visibility,
  listCount: group.list_count,
  canAddList: group.permissions.includes('add_list'),
  canSet: group.permissions.includes('settings'),
  canEdit: group.permissions.includes('edit'),
  canDelete: group.permissions.includes('delete'),
})

/** The lists a group shows this account, in the group's order. */
export async function fetchGroupLists(code: string): Promise<ListSummary[]> {
  const lists = await asAccount<ApiList[]>(`/api/v2/groups/${encodeURIComponent(code)}/lists/`)
  return lists.map(summary)
}

/** A list's links, in the list's order. */
export async function fetchLinks(code: string): Promise<LinkSummary[]> {
  const links = await everyPage<ApiLink>(`/api/v2/lists/${encodeURIComponent(code)}/links/`)
  return links.map(linkSummary)
}

const linkSummary = (link: ApiLink): LinkSummary => ({
  id: link.id,
  title: link.display.title,
  url: link.destination_url,
  site: link.display.site_name,
  shortUrl: link.short_url,
})

/**
 * Moves one link to `toIndex` (0-based) and answers with the links in their new order. The
 * site applies the move to the order it has now, so two people moving links never undo each
 * other, and writes one change to the list's history.
 */
export async function moveLink(code: string, id: string, toIndex: number): Promise<LinkSummary[]> {
  const links = await asAccount<ApiLink[]>(`/api/v2/lists/${encodeURIComponent(code)}/reorder/`, {
    method: 'POST',
    body: { link: id, to_index: toIndex },
  })
  return links.map(linkSummary)
}

/**
 * Removes a link from a list. Its short link stops working; the list's history on the site
 * keeps what the list was. Answers with the list as kept here, one link fewer.
 */
export async function removeLink(list: ListSummary, id: string): Promise<ListSummary> {
  await asAccount<null>(
    `/api/v2/lists/${encodeURIComponent(list.code)}/links/${encodeURIComponent(id)}/`,
    { method: 'DELETE' },
  )
  const now = { ...list, linkCount: Math.max(0, list.linkCount - 1) }
  await remember(now)
  return now
}

/** Creates a private list. `key` makes a retried request return the same list. */
/**
 * Makes a list that `visibility` says who can open: the user's answer in the form that made
 * it, never a default of this function's. The answer is offered again the next time.
 */
export async function createList(
  title: string,
  key: string,
  visibility: Visibility,
): Promise<ListSummary> {
  const created = summary(
    await asAccount<ApiList>('/api/v2/lists/', {
      method: 'POST',
      body: { title, visibility },
      idempotencyKey: key,
    }),
  )
  await remember(created)
  await saveNewListVisibility(visibility)
  return created
}

export interface SavedLink {
  id: string
  short_url: string | null
}

export type SaveOutcome =
  | { saved: true; link: SavedLink }
  /** The server wouldn't take this page in this list: already there, a full list, a blocked host. */
  | { saved: false; reason: string }

/**
 * Adds a page to a list. The title is the user's (the tab's, as they left it), so details the
 * site fetches later never replace it (invariant 6); without one, the site shows the page's
 * own. `key` makes a retry return the same link.
 */
export async function savePage(
  list: string,
  page: { url: string; title: string },
  key: string,
): Promise<SaveOutcome> {
  try {
    const link = await asAccount<SavedLink>(`/api/v2/lists/${encodeURIComponent(list)}/links/`, {
      method: 'POST',
      body: { destination_url: page.url, title: page.title.trim() || null },
      idempotencyKey: key,
    })
    await markUsed(list)
    return { saved: true, link }
  } catch (error) {
    // 400 is about this page or this list as they are; anything else is a failure to report.
    if (error instanceof ApiError && error.status === 400)
      return { saved: false, reason: error.userMessage }
    throw error
  }
}

/**
 * Chooses who can open a list. Only ever called for a choice the user just made: nothing in
 * the extension changes a list's visibility by itself (invariant 2). The server decides
 * whether this account may (a public list needs a verified email address).
 */
export async function setVisibility(code: string, visibility: Visibility): Promise<ListSummary> {
  const list = summary(
    await asAccount<ApiList>(`/api/v2/lists/${encodeURIComponent(code)}/`, {
      method: 'PATCH',
      body: { visibility },
    }),
  )
  await remember(list)
  return list
}

export type AddOutcome =
  | { added: true }
  /** The server wouldn't: already in the group, not this account's to share, a full group. */
  | { added: false; reason: string }

/** Adds a list to a group, at its end. */
export async function addToGroup(group: string, list: string): Promise<AddOutcome> {
  try {
    await asAccount(`/api/v2/groups/${encodeURIComponent(group)}/lists/`, {
      method: 'POST',
      body: { list },
    })
    return { added: true }
  } catch (error) {
    if (error instanceof ApiError && [400, 403, 409].includes(error.status))
      return { added: false, reason: error.userMessage }
    throw error
  }
}
