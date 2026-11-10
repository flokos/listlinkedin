// The account's lists and groups, and saving a page into a list.
import { asAccount } from './account'
import { ApiError } from './api'
import { cacheLists, getCachedLists, type ListSummary, markUsed, type Visibility } from './storage'

/** A list as /api/v2/ represents it (backend/apps/sharing/v2/serializers.py), as far as used. */
interface ApiList {
  code: string
  title: string
  url: string
  visibility: Visibility
  link_count: number
  /** What this account may do, from the server's policy: never re-derived here. */
  permissions: string[]
}

interface Page<T> {
  next: string | null
  results: T[]
}

export interface GroupSummary {
  code: string
  title: string
  listCount: number
}

/** The most links a list holds (backend/apps/sharing/domain.py). */
export const LINKS_PER_LIST = 100
const PAGE_SIZE = 100
const MAX_PAGES = 5

const summary = (list: ApiList): ListSummary => ({
  code: list.code,
  title: list.title,
  url: list.url,
  visibility: list.visibility,
  linkCount: list.link_count,
  canEdit: list.permissions.includes('edit'),
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

export async function fetchGroups(): Promise<GroupSummary[]> {
  const groups = await everyPage<{ code: string; title: string; list_count: number }>(
    '/api/v2/groups/',
  )
  return groups.map((group) => ({
    code: group.code,
    title: group.title,
    listCount: group.list_count,
  }))
}

/** The lists a group shows this account, in the group's order. */
export async function fetchGroupLists(code: string): Promise<ListSummary[]> {
  const lists = await asAccount<ApiList[]>(`/api/v2/groups/${encodeURIComponent(code)}/lists/`)
  return lists.map(summary)
}

/** Creates a private list. `key` makes a retried request return the same list. */
export async function createList(title: string, key: string): Promise<ListSummary> {
  const created = summary(
    await asAccount<ApiList>('/api/v2/lists/', {
      method: 'POST',
      body: { title },
      idempotencyKey: key,
    }),
  )
  const cached = (await getCachedLists()) ?? []
  await cacheLists([created, ...cached.filter((list) => list.code !== created.code)])
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
 * site fetches later never replace it (invariant 6). `key` makes a retry return the same link.
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
