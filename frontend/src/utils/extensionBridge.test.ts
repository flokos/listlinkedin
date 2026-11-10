import { afterEach, describe, expect, it } from 'vitest'

import {
  EXTENSION,
  type ExtensionMessage,
  extensionMessage,
  findExtension,
  PAGE,
  type PageMessage,
  sendCode,
} from './extensionBridge'

const CHALLENGE = 'c'.repeat(43)
const cleanups: (() => void)[] = []
afterEach(() => cleanups.splice(0).forEach((stop) => stop()))

const fromExtension = (data: unknown, init: MessageEventInit = {}) =>
  new MessageEvent('message', { data, origin: window.location.origin, source: window, ...init })

/**
 * Plays the extension's content script: hears what the page posts on this window and answers
 * with `reply`'s message, as coming from this window and origin unless `init` says otherwise.
 */
function fakeExtension(
  reply: (message: PageMessage) => Record<string, unknown> | undefined,
  init: MessageEventInit = {},
) {
  const heard: PageMessage[] = []
  const listener = (event: MessageEvent) => {
    const message = event.data as PageMessage
    if (message?.source !== PAGE) return
    heard.push(message)
    const answer = reply(message)
    if (answer)
      window.dispatchEvent(
        fromExtension({ source: EXTENSION, challenge: CHALLENGE, ...answer }, init),
      )
  }
  window.addEventListener('message', listener)
  cleanups.push(() => window.removeEventListener('message', listener))
  return heard
}

describe('findExtension', () => {
  it('says whether the extension started this request', async () => {
    const heard = fakeExtension(() => ({ type: 'ready', started: true }))
    expect(await findExtension(CHALLENGE)).toBe(true)
    expect(heard[0]).toEqual({ source: PAGE, type: 'hello', challenge: CHALLENGE })

    cleanups.splice(0).forEach((stop) => stop())
    fakeExtension(() => ({ type: 'ready', started: false }))
    expect(await findExtension(CHALLENGE)).toBe(false)
  })

  it('asks again until the extension has loaded', async () => {
    let asked = 0
    fakeExtension(() => (++asked < 3 ? undefined : { type: 'ready', started: true }))
    expect(await findExtension(CHALLENGE, 2000)).toBe(true)
    expect(asked).toBe(3)
  })

  it('finds none when nothing answers', async () => {
    expect(await findExtension(CHALLENGE, 60)).toBeNull()
  })

  it('ignores answers from another site, another window or about another request', async () => {
    const ready = { type: 'ready', started: true }
    fakeExtension(() => ready, { origin: 'https://evil.example' })
    fakeExtension(() => ready, { source: null })
    fakeExtension(() => ({ ...ready, challenge: 'x'.repeat(43) }))
    expect(await findExtension(CHALLENGE, 120)).toBeNull()
  })
})

describe('sendCode', () => {
  it('hands the code over and waits until the extension has connected', async () => {
    const heard = fakeExtension((message) =>
      message.type === 'code' ? { type: 'connected' } : undefined,
    )
    await sendCode(CHALLENGE, 'one-time-code')
    expect(heard).toEqual([
      { source: PAGE, type: 'code', challenge: CHALLENGE, code: 'one-time-code' },
    ])
  })

  it("fails with the extension's reason, or when it doesn't answer", async () => {
    fakeExtension(() => ({ type: 'failed', message: 'The code had expired.' }))
    await expect(sendCode(CHALLENGE, 'code')).rejects.toThrow('The code had expired.')

    cleanups.splice(0).forEach((stop) => stop())
    await expect(sendCode(CHALLENGE, 'code', 60)).rejects.toThrow("didn't answer")
  })
})

describe('extensionMessage', () => {
  const read = (data: unknown, init: MessageEventInit = {}) =>
    extensionMessage(fromExtension(data, init), CHALLENGE)
  const ready: ExtensionMessage = {
    source: EXTENSION,
    type: 'ready',
    challenge: CHALLENGE,
    started: true,
  }

  it('accepts only the shapes of the protocol', () => {
    expect(read(ready)).toEqual(ready)
    expect(read({ ...ready, started: 'yes', extra: 1 })).toEqual({ ...ready, started: false })
    expect(read({ ...ready, type: 'failed', message: 'x'.repeat(500) })?.type).toBe('failed')
    expect(read({ ...ready, type: 'other' })).toBeNull()
    expect(read({ ...ready, source: PAGE })).toBeNull()
    expect(read('ready')).toBeNull()
    expect(read(null)).toBeNull()
  })

  it('keeps a failure message short', () => {
    const failed = read({ ...ready, type: 'failed', message: 'x'.repeat(500) })
    expect(failed).toMatchObject({ type: 'failed', message: 'x'.repeat(200) })
  })
})
