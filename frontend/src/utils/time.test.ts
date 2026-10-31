import { describe, expect, it } from 'vitest'

import { endOfDay, expiryInfo, localDate } from './time'

const now = Date.parse('2026-10-28T12:00:00Z')
const inMs = (ms: number) => new Date(now + ms).toISOString()
const HOUR = 3_600_000
const DAY = 24 * HOUR

describe('expiryInfo', () => {
  it('shows a fresh list as 30 days', () => {
    expect(expiryInfo(inMs(30 * DAY - 60_000), now)).toEqual({
      label: 'Expires in 30 days',
      tone: 'normal',
    })
  })

  it('warns under three days and switches to hours under two', () => {
    expect(expiryInfo(inMs(2.5 * DAY), now)).toEqual({
      label: 'Expires in 3 days',
      tone: 'warning',
    })
    expect(expiryInfo(inMs(30 * HOUR), now)).toEqual({
      label: 'Expires in 30 hours',
      tone: 'warning',
    })
    expect(expiryInfo(inMs(30 * 60_000), now).label).toBe('Expires in less than an hour')
  })

  it('reports expired lists', () => {
    expect(expiryInfo(inMs(-1), now)).toEqual({ label: 'Expired', tone: 'expired' })
  })
})

describe('expiry dates', () => {
  it('round-trips a local calendar date through the end of that day', () => {
    const iso = endOfDay('2026-11-03')
    const end = new Date(iso)
    expect([end.getFullYear(), end.getMonth(), end.getDate(), end.getHours()]).toEqual([
      2026, 10, 3, 23,
    ])
    expect(localDate(iso)).toBe('2026-11-03')
  })
})
