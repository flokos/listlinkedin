import { beforeEach, describe, expect, it, vi } from 'vitest'

import { cacheLists, markUsed, saveConnection } from '../lib/storage'
import { ADA, browser, json } from '../test/fakeBrowser'
import { listSummary, site } from '../test/site'

// The module remembers what it built last: each test starts with a new one.
let menus: typeof import('./menus')
beforeEach(async () => {
  vi.resetModules()
  menus = await import('./menus')
})

const built = () => browser().contextMenus.menus
const titles = (parentId?: string) =>
  built()
    .filter((entry) => entry.parentId === parentId)
    .map((entry) => entry.title ?? `(${entry.type})`)

describe('menuItems', () => {
  it('offers one entry, on pages and links, while the browser is not connected', () => {
    expect(menus.menuItems({ connected: false, lists: [listSummary('A')], recent: ['A'] })).toEqual(
      [{ id: 'choose', title: 'Save to listlinkedin…', contexts: ['page', 'link'] }],
    )
  })

  it('offers the lists saved to last first, then "Choose a list…"', () => {
    const lists = [
      listSummary('A'),
      listSummary('V', { canEdit: false }), // can't be saved to: not offered
      listSummary('B'),
      listSummary('C'),
    ]
    const items = menus.menuItems({ connected: true, lists, recent: ['V', 'C'] })

    expect(items.filter((item) => item.parentId === 'save').map((item) => item.id)).toEqual([
      'save-to:C',
      'save-to:A',
      'save-to:B',
      'separator',
      'choose',
      'separator-several',
      'several:tabs',
      'several:history',
    ])
    expect(items[0]).toEqual({
      id: 'save',
      title: 'Save to listlinkedin',
      contexts: ['page', 'link'],
    })
    // On the toolbar button. The list saved to last was V, which can still be shared.
    expect(items.filter((item) => item.contexts[0] === 'action')).toEqual([
      { id: 'copy-link', title: 'Copy link to “List V”', contexts: ['action'] },
      { id: 'several:tabs:button', title: 'Save open tabs…', contexts: ['action'] },
      { id: 'several:history:button', title: 'Save from history…', contexts: ['action'] },
      { id: 'my-lists', title: 'Open my lists', contexts: ['action'] },
    ])
  })

  it('offers at most six lists, and no "Copy link" before anything was saved from here', () => {
    const lists = 'ABCDEFGH'.split('').map((code) => listSummary(code))
    const items = menus.menuItems({ connected: true, lists, recent: [] })
    expect(items.filter((item) => item.id.startsWith('save-to:'))).toHaveLength(6)
    expect(items.map((item) => item.id)).not.toContain('copy-link')
  })

  it('has only "Choose a list…" for an account without a list to save to', () => {
    const items = menus.menuItems({ connected: true, lists: [], recent: [] })
    expect(items.map((item) => item.id)).toEqual([
      'save',
      'choose',
      'separator-several',
      'several:tabs',
      'several:history',
      'several:tabs:button',
      'several:history:button',
      'my-lists',
    ])
    // Chrome shows no more than six of an extension's entries on its toolbar button.
    const onButton = menus.menuItems({ connected: true, lists: [listSummary('A')], recent: ['A'] })
    expect(onButton.filter((item) => item.contexts[0] === 'action')).toHaveLength(4)
  })
})

describe('menuTitle', () => {
  it('keeps a title from being read as a menu command', () => {
    expect(menus.menuTitle('Tools & tips')).toBe('Tools && tips')
    expect(menus.menuTitle('100%sure')).toBe('100%​sure')
    expect(menus.menuTitle('x'.repeat(60))).toBe(`${'x'.repeat(39)}…`)
  })
})

describe('rebuildMenus', () => {
  it('makes the menus from what is kept in the browser', async () => {
    await menus.rebuildMenus()
    expect(titles()).toEqual(['Save to listlinkedin…'])

    await saveConnection(ADA)
    await cacheLists([listSummary('A', { title: 'Reading' }), listSummary('B', { title: 'Work' })])
    await markUsed('B')
    await menus.rebuildMenus()

    expect(titles()).toEqual([
      'Save to listlinkedin',
      'Copy link to “Work”',
      'Save open tabs…',
      'Save from history…',
      'Open my lists',
    ])
    expect(titles('save')).toEqual([
      'Work',
      'Reading',
      '(separator)',
      'Choose a list…',
      '(separator)',
      'Save open tabs…',
      'Save from history…',
    ])
  })

  it('leaves the menus alone when nothing they show has changed, unless told to', async () => {
    await menus.rebuildMenus()
    await menus.rebuildMenus()
    expect(browser().contextMenus.removeAll).toHaveBeenCalledOnce()

    await menus.rebuildMenus(true) // after an install or a browser start
    expect(browser().contextMenus.removeAll).toHaveBeenCalledTimes(2)
    expect(titles()).toEqual(['Save to listlinkedin…'])
  })

  it('builds one after the other when asked twice at once', async () => {
    await saveConnection(ADA)
    await cacheLists([listSummary('A')])
    await Promise.all([menus.rebuildMenus(true), menus.rebuildMenus(true)])
    // Each id once: the second build removed everything before adding again.
    const ids = built().map((entry) => entry.id)
    expect(ids).toEqual([...new Set(ids)])
    expect(ids).toContain('save-to:A')
  })
})

describe('onMenuClick', () => {
  beforeEach(async () => {
    await saveConnection(ADA)
    await cacheLists([listSummary('A')])
  })

  it('saves the page that was right-clicked, with its title', async () => {
    const { calls, bodies } = site({
      'POST /api/v2/lists/A/links/': () => json({ id: 'l1', short_url: null }, 201),
    })
    await menus.onMenuClick(
      { menuItemId: 'save-to:A', pageUrl: 'https://example.com/page' },
      { url: 'https://example.com/page', title: 'A page' },
    )
    expect(calls).toEqual(['POST /api/v2/lists/A/links/'])
    expect(bodies[0]).toEqual({ destination_url: 'https://example.com/page', title: 'A page' })
    expect(browser().action.badge.text).toBe('✓')
  })

  it("saves a link that was right-clicked by its address, not under the page's title", async () => {
    const { bodies } = site({
      'POST /api/v2/lists/A/links/': () => json({ id: 'l1', short_url: null }, 201),
    })
    await menus.onMenuClick(
      {
        menuItemId: 'save-to:A',
        pageUrl: 'https://example.com/page',
        linkUrl: 'https://example.org/elsewhere',
      },
      { url: 'https://example.com/page', title: 'A page' },
    )
    // No title: the list shows the linked page's own once the site has fetched it.
    expect(bodies[0]).toEqual({ destination_url: 'https://example.org/elsewhere', title: null })
  })

  it('opens the window to choose a list in, about the link or the page', async () => {
    await menus.onMenuClick(
      { menuItemId: 'choose', pageUrl: 'https://example.com/page' },
      { url: 'https://example.com/page', title: 'A page' },
    )
    expect(browser().windows.create).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'popup',
        url: 'chrome-extension://fake-extension-id/popup.html?url=https%3A%2F%2Fexample.com%2Fpage&title=A+page',
      }),
    )
  })

  it('opens "My lists" on the site from the toolbar button', async () => {
    await menus.onMenuClick({ menuItemId: 'my-lists' })
    expect(browser().tabs.create).toHaveBeenCalledWith({ url: 'https://lists.example.test/lists' })
  })

  it('opens the page for saving several, on the open tabs or on the history', async () => {
    await menus.onMenuClick({ menuItemId: 'several:tabs', pageUrl: 'https://example.com/page' })
    expect(browser().tabs.create).toHaveBeenLastCalledWith({
      url: 'chrome-extension://fake-extension-id/picker.html?source=tabs',
    })
    await menus.onMenuClick({ menuItemId: 'several:history:button' }) // on the toolbar button
    expect(browser().tabs.create).toHaveBeenLastCalledWith({
      url: 'chrome-extension://fake-extension-id/picker.html?source=history',
    })
    // It only opens the page: nothing is read or sent by the click.
    expect(browser().tabs.query).not.toHaveBeenCalled()
  })

  it('does nothing for an entry it does not know', async () => {
    const { calls } = site({})
    await menus.onMenuClick({ menuItemId: 'separator' })
    expect(calls).toEqual([])
    expect(browser().tabs.create).not.toHaveBeenCalled()
  })
})
