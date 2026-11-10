import { beforeAll, describe, expect, it } from 'vitest'

import { EXTENSION, type ExtensionMessage, PAGE } from '../lib/bridge'
import { browser } from '../test/fakeBrowser'

const challenge = 'c'.repeat(43)

/** What the content script posts back on the window, in order. */
function heard(): ExtensionMessage[] {
  const messages: ExtensionMessage[] = []
  window.addEventListener('message', (event: MessageEvent) => {
    if ((event.data as ExtensionMessage | null)?.source === EXTENSION) messages.push(event.data)
  })
  return messages
}

/** The page posting to its own window, as a browser delivers it. */
const fromPage = (data: unknown, init: MessageEventInit = {}) =>
  window.dispatchEvent(
    new MessageEvent('message', { data, origin: window.location.origin, source: window, ...init }),
  )

const settled = () => new Promise((resolve) => setTimeout(resolve, 20))

beforeAll(async () => {
  await import('./bridge') // adds its listener once; it reads `chrome` on every message
})

describe('the content script', () => {
  it('asks the background script whether the extension started the request', async () => {
    const messages = heard()
    browser().runtime.sendMessage.mockResolvedValue({ started: true })

    fromPage({ source: PAGE, type: 'hello', challenge })
    await settled()

    expect(browser().runtime.sendMessage).toHaveBeenCalledWith({
      type: 'connect:started',
      challenge,
    })
    expect(messages).toEqual([{ source: EXTENSION, type: 'ready', challenge, started: true }])
  })

  it("says it didn't, when the background script says so or can't be reached", async () => {
    const messages = heard()
    browser().runtime.sendMessage.mockResolvedValueOnce({ started: false })
    fromPage({ source: PAGE, type: 'hello', challenge })
    await settled()
    browser().runtime.sendMessage.mockRejectedValueOnce(new Error('Extension context invalidated'))
    fromPage({ source: PAGE, type: 'hello', challenge })
    await settled()

    expect(messages.map((message) => message.type === 'ready' && message.started)).toEqual([
      false,
      false,
    ])
  })

  it('passes the code on and reports how the exchange went', async () => {
    const messages = heard()
    browser().runtime.sendMessage.mockResolvedValueOnce({ ok: true })
    fromPage({ source: PAGE, type: 'code', challenge, code: 'one-time-code' })
    await settled()
    browser().runtime.sendMessage.mockResolvedValueOnce({ ok: false, message: 'It expired.' })
    fromPage({ source: PAGE, type: 'code', challenge, code: 'one-time-code' })
    await settled()

    expect(browser().runtime.sendMessage).toHaveBeenCalledWith({
      type: 'connect:code',
      challenge,
      code: 'one-time-code',
    })
    expect(messages).toEqual([
      { source: EXTENSION, type: 'connected', challenge },
      { source: EXTENSION, type: 'failed', challenge, message: 'It expired.' },
    ])
  })

  it('ignores other windows, other sites and anything that is not the protocol', async () => {
    const messages = heard()
    const hello = { source: PAGE, type: 'hello', challenge }

    fromPage(hello, { origin: 'https://evil.example' })
    fromPage(hello, { source: null })
    fromPage({ ...hello, source: 'someone-else' })
    fromPage({ ...hello, challenge: 'short' })
    fromPage('hello')
    await settled()

    expect(browser().runtime.sendMessage).not.toHaveBeenCalled()
    expect(messages).toEqual([])
  })
})
