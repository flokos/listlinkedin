import { describe, expect, it } from 'vitest'

import { effectiveSort, exploreQuery, orderingFor, parseExplore, sortOptions } from './explore'

describe('Explore address', () => {
  it('reads the defaults from a bare /explore', () => {
    expect(parseExplore({})).toEqual({ kind: 'lists', q: '', tags: [], sort: null })
    expect(exploreQuery(parseExplore({}))).toEqual({})
  })

  it('normalizes tags like the server and ignores unknown values', () => {
    const state = parseExplore({
      in: 'groups',
      q: '  docker ',
      tags: 'Dev,web_dev,,dev',
      sort: 'x',
    })
    expect(state).toEqual({ kind: 'groups', q: 'docker', tags: ['dev', 'web-dev'], sort: null })
    expect(parseExplore({ in: 'people' }).kind).toBe('lists')
  })

  it('round-trips a search', () => {
    const query = { in: 'groups', q: 'docker', tags: 'dev,ai', sort: 'name' }
    expect(exploreQuery(parseExplore(query))).toEqual(query)
  })

  it('sorts by best match only while searching', () => {
    expect(effectiveSort(parseExplore({}))).toBe('recent')
    expect(effectiveSort(parseExplore({ q: 'docker' }))).toBe('relevance')
    expect(effectiveSort(parseExplore({ sort: 'relevance' }))).toBe('recent')
    expect(orderingFor(parseExplore({ q: 'docker', sort: 'name' }))).toBe('title')
    expect(sortOptions(false).map((o) => o.value)).toEqual(['recent', 'name'])
    expect(sortOptions(true).map((o) => o.value)).toEqual(['relevance', 'recent', 'name'])
  })
})
