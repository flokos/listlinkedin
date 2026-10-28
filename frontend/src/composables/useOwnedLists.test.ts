import { beforeEach, describe, expect, it } from 'vitest'

import { STORAGE_KEY, useOwnedLists } from './useOwnedLists'

const entry = { code: 'abc', token: 'tok', title: 'Team', expiresAt: '2026-12-01T00:00:00Z' }

describe('useOwnedLists', () => {
  beforeEach(() => {
    localStorage.clear()
    useOwnedLists().reload()
  })

  it('saves, finds and forgets lists, persisting to localStorage', () => {
    const owned = useOwnedLists()
    owned.save(entry)
    expect(owned.tokenFor('abc')).toBe('tok')
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!).abc.token).toBe('tok')
    owned.forget('abc')
    expect(owned.tokenFor('abc')).toBeUndefined()
    expect(owned.count.value).toBe(0)
  })

  it('keeps the original saved time when a token is replaced', () => {
    const owned = useOwnedLists()
    owned.save({ ...entry, savedAt: '2026-01-01T00:00:00Z' })
    owned.update('abc', { token: 'new' })
    expect(owned.get('abc')).toMatchObject({ token: 'new', savedAt: '2026-01-01T00:00:00Z' })
  })

  it('lists most recently saved first', () => {
    const owned = useOwnedLists()
    owned.save({ ...entry, code: 'old', savedAt: '2026-01-01T00:00:00Z' })
    owned.save({ ...entry, code: 'new', savedAt: '2026-02-01T00:00:00Z' })
    expect(owned.lists.value.map((l) => l.code)).toEqual(['new', 'old'])
  })

  it('picks up changes made in another tab', () => {
    const owned = useOwnedLists()
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ abc: { ...entry, savedAt: 'x' } }))
    window.dispatchEvent(new StorageEvent('storage', { key: STORAGE_KEY }))
    expect(owned.tokenFor('abc')).toBe('tok')
  })

  it('ignores corrupt storage', () => {
    localStorage.setItem(STORAGE_KEY, '{not json')
    const owned = useOwnedLists()
    owned.reload()
    expect(owned.count.value).toBe(0)
  })
})
