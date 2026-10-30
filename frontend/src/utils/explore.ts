// Explore's state lives in the address (?q=…&tags=a,b&sort=name&in=groups), so a search can be
// shared and Back returns to it. These turn the query into a search and back.
import type { LocationQuery, LocationQueryRaw } from 'vue-router'

import { type DirectoryKind, type DirectoryOrdering, normalizeTag } from '../api'

export type ExploreSort = 'relevance' | 'recent' | 'name'

export interface ExploreState {
  kind: DirectoryKind
  q: string
  tags: string[]
  /** What the reader chose; `null` is the default (best match when searching, else recent). */
  sort: ExploreSort | null
}

const ORDERING: Record<ExploreSort, DirectoryOrdering> = {
  relevance: '-relevance',
  recent: '-updated_at',
  name: 'title',
}

const first = (value: LocationQuery[string] | undefined) =>
  (Array.isArray(value) ? value[0] : value) ?? ''

export function parseExplore(query: LocationQuery): ExploreState {
  const sort = first(query.sort)
  const tags: string[] = []
  for (const tag of first(query.tags).split(',').map(normalizeTag)) {
    if (tag && !tags.includes(tag)) tags.push(tag)
  }
  return {
    kind: first(query.in) === 'groups' ? 'groups' : 'lists',
    q: first(query.q).trim(),
    tags,
    sort: sort in ORDERING ? (sort as ExploreSort) : null,
  }
}

/** The address for a state: defaults are left out, so plain /explore is the default. */
export function exploreQuery(state: ExploreState): LocationQueryRaw {
  const query: LocationQueryRaw = {}
  if (state.kind === 'groups') query.in = 'groups'
  if (state.q) query.q = state.q
  if (state.tags.length) query.tags = state.tags.join(',')
  if (state.sort) query.sort = state.sort
  return query
}

/** The sort in effect: "best match" means nothing without search words. */
export function effectiveSort(state: ExploreState): ExploreSort {
  if (state.sort === 'relevance' && !state.q) return 'recent'
  return state.sort ?? (state.q ? 'relevance' : 'recent')
}

export const orderingFor = (state: ExploreState): DirectoryOrdering =>
  ORDERING[effectiveSort(state)]

export function sortOptions(searching: boolean): { value: ExploreSort; title: string }[] {
  return [
    ...(searching ? [{ value: 'relevance' as const, title: 'Best match' }] : []),
    { value: 'recent', title: 'Recently updated' },
    { value: 'name', title: 'Name' },
  ]
}
