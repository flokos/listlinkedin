// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { startConnect } from '../lib/connect'
import { cacheLists, getConnection, getPending, markUsed, saveConnection } from '../lib/storage'
import { ADA, browser, json, type Sender } from '../test/fakeBrowser'
import { listSummary, site } from '../test/site'

const sitePage: Sender = {
  id: 'fake-extension-id',
  url: 'https://lists.example.test/connect-browser?challenge=x',
  frameId: 0,
  tab: { id: 7 },
}

/** Sends a message as the browser would, and resolves with the answer (or `false`: ignored). */
function send(message: unknown, sender: Sender = sitePage): Promise<unknown> {
  return new Promise((resolve) => {
    const [kept] = browser().runtime.onMessage.fire(message, sender, resolve)
    if (kept !== true) resolve(false)
  })
}

beforeEach(async () => {
  vi.resetModules() // the script adds its listeners when it loads: once per fake browser
  await import('./index')
})

describe('the background script', () => {
  it('opens the welcome page when the extension is installed, not when it is updated', () => {
    browser().runtime.onInstalled.fire({ reason: 'update' })
    expect(browser().tabs.create).not.toHaveBeenCalled()

    browser().runtime.onInstalled.fire({ reason: 'install' })
    expect(browser().tabs.create).toHaveBeenCalledWith({
      url: 'chrome-extension://fake-extension-id/welcome.html',
    })
  })

  it('tells the Connect page whether this extension started the request', async () => {
    await startConnect()
    const { challenge } = (await getPending())!

    expect(await send({ type: 'connect:started', challenge })).toEqual({ started: true })
    expect(await send({ type: 'connect:started', challenge: 'x'.repeat(43) })).toEqual({
      started: false,
    })
  })

  it('exchanges the code it is handed and says how it went', async () => {
    await startConnect()
    const { challenge } = (await getPending())!
    const connected = {
      id: 'browser-1',
      name: 'Firefox on Linux',
      session_token: 'the-session-token',
      user: { email: 'ada@example.com' },
    }
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => json(connected, 201)),
    )

    expect(await send({ type: 'connect:code', challenge, code: 'the-code' })).toEqual({ ok: true })
    expect((await getConnection())?.token).toBe('the-session-token')
    // The request is over: the same code, or another, is refused without asking the site.
    expect(await send({ type: 'connect:code', challenge, code: 'the-code' })).toEqual({
      ok: false,
      message: 'This request has expired. Choose Connect in the extension again.',
    })
  })

  it("answers only its own content script on the site's pages", async () => {
    await startConnect()
    const { challenge } = (await getPending())!
    const ask = { type: 'connect:started', challenge }

    for (const sender of [
      { ...sitePage, url: 'https://evil.example/connect-browser' },
      { ...sitePage, id: 'another-extension' },
      { ...sitePage, frameId: 3 },
      { ...sitePage, tab: undefined }, // an extension page, not a tab's content script
    ])
      expect(await send(ask, sender), JSON.stringify(sender)).toBe(false)
    // And only the protocol's messages.
    expect(await send({ type: 'something-else', challenge })).toBeUndefined()
  })

  it('makes the menus on install and on browser start, and again when what they show changes', async () => {
    const menus = () => browser().contextMenus.menus.map((entry) => entry.id)

    browser().runtime.onInstalled.fire({ reason: 'update' })
    await vi.waitFor(() => expect(menus()).toEqual(['choose'])) // not connected yet

    await saveConnection(ADA)
    await cacheLists([listSummary('A')])
    await vi.waitFor(() => expect(menus()).toContain('save-to:A'))

    browser().contextMenus.menus.splice(0) // as if the browser had lost them
    browser().runtime.onStartup.fire()
    await vi.waitFor(() => expect(menus()).toContain('save-to:A'))

    // Something the menus don't show changes nothing.
    const before = browser().contextMenus.removeAll.mock.calls.length
    await browser().storage.local.set({ somethingElse: 1 })
    await browser().storage.session.set({ connection: 'not the local one' })
    await new Promise((resolve) => setTimeout(resolve, 10))
    expect(browser().contextMenus.removeAll.mock.calls.length).toBe(before)
  })

  it('does what a menu entry and a shortcut ask', async () => {
    await saveConnection(ADA)
    await cacheLists([listSummary('A')])
    await markUsed('A')
    const { calls } = site({
      'POST /api/v2/lists/A/links/': () => json({ id: 'l1', short_url: null }, 201),
    })
    const saved = () => calls.filter((call) => call === 'POST /api/v2/lists/A/links/').length

    browser().contextMenus.onClicked.fire(
      { menuItemId: 'save-to:A', pageUrl: 'https://example.com/a' },
      { url: 'https://example.com/a', title: 'A' },
    )
    await vi.waitFor(() => expect(saved()).toBe(1))

    browser().commands.onCommand.fire('save-page', { url: 'https://example.com/b', title: 'B' })
    await vi.waitFor(() => expect(saved()).toBe(2))

    // No document here, as in Chrome's service worker: copying goes through the offscreen one.
    browser().runtime.sendMessage.mockResolvedValue({ ok: true })
    browser().commands.onCommand.fire('copy-list-link')
    await vi.waitFor(() =>
      expect(browser().runtime.sendMessage).toHaveBeenCalledWith({
        type: 'offscreen:copy',
        text: 'https://lists.example.test/l/A',
      }),
    )
  })
})
