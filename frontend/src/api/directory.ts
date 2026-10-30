// The public directory behind Explore, /api/v2/directory/ (docs/v2/09-API-DESIGN.md#directory).
// Anyone may read it; it lists public lists and groups only. Rate-limited per IP (429).
import { request } from './client'
import type { GroupDetail } from './groups'
import type { ListDetail, Page } from './lists'

export type DirectoryKind = 'lists' | 'groups'
/** `-relevance` needs a search text; without one the server orders by `-updated_at`. */
export type DirectoryOrdering = '-relevance' | '-updated_at' | 'title'

export interface DirectoryQuery {
  q?: string
  tags?: string[]
  ordering?: DirectoryOrdering
  page?: number
}

export interface TagCount {
  tag: string
  count: number
}

/** Tags as the server stores them (backend/apps/sharing/domain.py). */
export const TAG_LIMITS = { perItem: 10, length: 32 } as const

/** What the server makes of a typed tag: "Dev Tools" → "dev-tools". Invalid input is left
 * for the server to refuse, with its message. */
export const normalizeTag = (tag: string) =>
  tag
    .trim()
    .toLowerCase()
    .replace(/[\s_]+/g, '-')

function search(query: DirectoryQuery): string {
  const params = new URLSearchParams()
  if (query.q) params.set('q', query.q)
  if (query.tags?.length) params.set('tags', query.tags.join(','))
  if (query.ordering) params.set('ordering', query.ordering)
  if (query.page && query.page > 1) params.set('page', String(query.page))
  const text = params.toString()
  return text ? `?${text}` : ''
}

export function directory(
  kind: 'lists',
  query: DirectoryQuery,
  signal?: AbortSignal,
): Promise<Page<ListDetail>>
export function directory(
  kind: 'groups',
  query: DirectoryQuery,
  signal?: AbortSignal,
): Promise<Page<GroupDetail>>
export function directory(kind: DirectoryKind, query: DirectoryQuery, signal?: AbortSignal) {
  return request<Page<ListDetail | GroupDetail>>(`/api/v2/directory/${kind}/${search(query)}`, {
    signal,
  })
}

/** The most used tags on public lists and groups (at most 30), optionally by prefix. */
export const popularTags = (prefix = '', signal?: AbortSignal) =>
  request<TagCount[]>(
    `/api/v2/directory/tags/${prefix ? `?prefix=${encodeURIComponent(prefix)}` : ''}`,
    { signal },
  )
