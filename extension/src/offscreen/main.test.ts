import { beforeEach, describe, expect, it, vi } from 'vitest'

import { browser, type Sender } from '../test/fakeBrowser'

const background: Sender = { id: 'fake-extension-id' }

function send(message: unknown, sender: Sender = background) {
  const respond = vi.fn()
  const [kept] = browser().runtime.onMessage.fire(message, sender, respond)
  return { kept, respond }
}

beforeEach(async () => {
  vi.resetModules() // the script adds its listener when it loads: once per fake browser
  await import('./main')
})

describe('the offscreen document', () => {
  it('copies what the background script sends and says whether it worked', () => {
    const copied: string[] = []
    document.execCommand = vi.fn(() => {
      copied.push(document.querySelector('textarea')?.value ?? '')
      return true
    })

    const { respond } = send({ type: 'offscreen:copy', text: 'https://lists.example.test/l/A' })

    expect(copied).toEqual(['https://lists.example.test/l/A'])
    expect(respond).toHaveBeenCalledWith({ ok: true })
  })

  it('ignores everything else, and everyone else', () => {
    document.execCommand = vi.fn(() => true)
    const copy = { type: 'offscreen:copy', text: 'x' }

    // The Connect page's messages are for the background script.
    expect(send({ type: 'connect:started', challenge: 'c'.repeat(43) }).kept).toBe(false)
    // A content script (it has a tab), and another extension.
    expect(send(copy, { ...background, tab: { id: 3 } }).kept).toBe(false)
    expect(send(copy, { id: 'another-extension' }).kept).toBe(false)
    expect(document.execCommand).not.toHaveBeenCalled()
  })
})
