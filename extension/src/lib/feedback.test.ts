import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { browser } from '../test/fakeBrowser'
import { clearMark, done, DONE_FOR, problem } from './feedback'
import { takeOutcome } from './storage'

beforeEach(() => void vi.useFakeTimers({ now: new Date('2026-11-11T10:00:00Z') }))
afterEach(() => void vi.useRealTimers())

const badge = () => browser().action.badge

describe('feedback without a window', () => {
  it('marks a success for a moment and keeps nothing to tell', async () => {
    await done()
    expect(badge().text).toBe('✓')

    await vi.advanceTimersByTimeAsync(DONE_FOR)
    expect(badge().text).toBe('')
    expect(await takeOutcome()).toBeNull()
  })

  it('keeps a note that is worth reading after a success', async () => {
    await done('You copied the link to “Reading”.')
    expect(badge().text).toBe('✓')
    expect(await takeOutcome()).toMatchObject({
      tone: 'info',
      text: 'You copied the link to “Reading”.',
    })
  })

  it('marks a problem until the popup is opened, and says it once', async () => {
    await problem("example.com wasn't saved.")
    await vi.advanceTimersByTimeAsync(60_000)
    expect(badge().text).toBe('!')

    expect(await takeOutcome()).toMatchObject({ tone: 'error', text: "example.com wasn't saved." })
    expect(await takeOutcome()).toBeNull() // told once
    await clearMark()
    expect(badge().text).toBe('')
  })

  it('forgets a problem nobody looked at for ten minutes', async () => {
    await problem('Too many requests.', 'info')
    await vi.advanceTimersByTimeAsync(10 * 60_000 + 1)
    expect(await takeOutcome()).toBeNull()
  })

  it('keeps the outcome out of what survives the browser session', async () => {
    await problem('Something went wrong.')
    expect([...browser().storage.local.data.keys()]).toEqual([])
    expect([...browser().storage.session.data.keys()]).toEqual(['outcome'])
  })
})
