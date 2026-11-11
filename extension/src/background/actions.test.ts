import { beforeEach, describe, expect, it, vi } from 'vitest'

import { cacheLists, getConnection, markUsed, saveConnection, takeOutcome } from '../lib/storage'
import { ADA, browser, json } from '../test/fakeBrowser'
import { listSummary, site } from '../test/site'
import {
  copyLastListLink,
  openChooser,
  runCommand,
  saveTo,
  saveToLastList,
  shortAddress,
} from './actions'

const PAGE = { url: 'https://example.com/article', title: 'An article' }
const ADD_TO_A = 'POST /api/v2/lists/A/links/'
const badge = () => browser().action.badge.text

/** The clipboard of a page (jsdom): what was written to it. */
function clipboard(works = true) {
  const written: string[] = []
  vi.stubGlobal('navigator', {
    clipboard: {
      writeText: vi.fn(async (text: string) => {
        if (!works) throw new Error('not allowed')
        written.push(text)
      }),
    },
  })
  return written
}

beforeEach(async () => {
  await saveConnection(ADA)
  await cacheLists([listSummary('A', { title: 'Reading' }), listSummary('B')])
})

describe('saveTo', () => {
  it('saves the page to the list and marks the button, with nothing left to tell', async () => {
    const { calls, bodies } = site({ [ADD_TO_A]: () => json({ id: 'l1', short_url: null }, 201) })

    await saveTo('A', PAGE)

    expect(calls).toEqual([ADD_TO_A])
    expect(bodies[0]).toEqual({ destination_url: PAGE.url, title: 'An article' })
    expect(badge()).toBe('✓')
    expect(await takeOutcome()).toBeNull()
  })

  it("says why when the site won't take the page", async () => {
    site({ [ADD_TO_A]: () => json({ destination_url: ['This URL is already in the list.'] }, 400) })

    await saveTo('A', PAGE)

    expect(badge()).toBe('!')
    expect(await takeOutcome()).toMatchObject({
      tone: 'info',
      text: "example.com/article wasn't saved to “Reading”. This URL is already in the list.",
    })
  })

  it("doesn't ask the site for a page it can't take", async () => {
    const { calls } = site({})
    await saveTo('A', { url: 'about:blank', title: '' })
    expect(calls).toEqual([])
    expect(badge()).toBe('!')
    expect((await takeOutcome())?.text).toContain('Only web pages')
  })

  it('says so when the connection is over, and when the site is out of reach', async () => {
    site({ [ADD_TO_A]: () => json({ detail: 'Sign in.' }, 401) })
    await saveTo('A', PAGE)
    expect((await takeOutcome())?.text).toBe("This browser isn't connected to listlinkedin yet.")
    expect(await getConnection()).toBeNull()

    await saveConnection(ADA) // connected again: the lists are read again too
    await cacheLists([listSummary('A', { title: 'Reading' })])
    site({ [ADD_TO_A]: () => new TypeError('Failed to fetch') })
    await saveTo('A', PAGE)
    expect(await takeOutcome()).toMatchObject({
      tone: 'error',
      text: "example.com/article wasn't saved to “Reading”. Couldn't reach listlinkedin. Check your connection and try again.",
    })
  })

  it('uses a new key for every click', async () => {
    site({ [ADD_TO_A]: () => json({ id: 'l1', short_url: null }, 201) })
    await saveTo('A', PAGE)
    await saveTo('A', PAGE)
    const keys = vi
      .mocked(fetch)
      .mock.calls.map(([, init]) => (init!.headers as Record<string, string>)['Idempotency-Key'])
    expect(new Set(keys).size).toBe(2)
  })
})

describe('saveToLastList', () => {
  it('saves to the list saved to last', async () => {
    await markUsed('A')
    const { calls } = site({ [ADD_TO_A]: () => json({ id: 'l1', short_url: null }, 201) })
    await saveToLastList(PAGE)
    expect(calls).toEqual([ADD_TO_A])
  })

  it('never picks a list by itself', async () => {
    const { calls } = site({})

    await saveToLastList(PAGE) // lists, but none saved to from here
    expect((await takeOutcome())?.text).toContain('Save a page from here once')

    await cacheLists([listSummary('A', { canEdit: false })])
    await markUsed('A')
    await saveToLastList(PAGE) // the last one can no longer be added to
    expect((await takeOutcome())?.text).toContain('Save a page from here once')

    expect(calls).toEqual([])
    expect(badge()).toBe('!')
  })

  it('asks to connect first when the browser is not connected', async () => {
    await browser().storage.local.remove('connection')
    await saveToLastList(PAGE)
    expect((await takeOutcome())?.text).toBe("This browser isn't connected to listlinkedin yet.")
  })
})

describe('copyLastListLink', () => {
  it("copies the list's address and changes nothing on the site", async () => {
    await cacheLists([listSummary('A', { title: 'Reading', visibility: 'unlisted' })])
    await markUsed('A')
    const written = clipboard()
    const { calls } = site({})

    await copyLastListLink()

    expect(written).toEqual(['https://lists.example.test/l/A'])
    expect(calls).toEqual([]) // copying is not sharing: who can open it stays as it is
    expect(badge()).toBe('✓')
    expect(await takeOutcome()).toBeNull()
  })

  it('adds that a private list opens for nobody new', async () => {
    await markUsed('A')
    clipboard()
    await copyLastListLink()
    expect(badge()).toBe('✓')
    expect(await takeOutcome()).toMatchObject({
      tone: 'info',
      text: 'You copied the link to “Reading”. Only people you add can open this link.',
    })
  })

  it('reports a clipboard the browser keeps shut, and a missing last list', async () => {
    await copyLastListLink()
    expect((await takeOutcome())?.text).toContain('Save a page from here once')

    await markUsed('A')
    clipboard(false)
    await copyLastListLink()
    expect(badge()).toBe('!')
    expect((await takeOutcome())?.text).toBe(
      "The browser didn't let the extension copy the link to “Reading”.",
    )
  })
})

describe('runCommand', () => {
  it('saves the tab the browser passes, or looks up the one in front', async () => {
    await markUsed('A')
    const { bodies } = site({ [ADD_TO_A]: () => json({ id: 'l1', short_url: null }, 201) })

    await runCommand('save-page', { url: 'https://example.com/passed', title: 'Passed' })
    expect(browser().tabs.query).not.toHaveBeenCalled()

    browser().tabs.query.mockResolvedValue([{ url: 'https://example.com/front', title: 'Front' }])
    await runCommand('save-page')
    expect(browser().tabs.query).toHaveBeenCalledWith({ active: true, lastFocusedWindow: true })

    expect(bodies).toEqual([
      { destination_url: 'https://example.com/passed', title: 'Passed' },
      { destination_url: 'https://example.com/front', title: 'Front' },
    ])
  })

  it('copies on the copy shortcut and ignores names it does not know', async () => {
    await markUsed('A')
    const written = clipboard()
    await runCommand('copy-list-link')
    await runCommand('something-else')
    expect(written).toEqual(['https://lists.example.test/l/A'])
  })
})

describe('openChooser', () => {
  it('opens the popup about the page in a small window of its own', async () => {
    await openChooser({ url: 'https://example.com/a?b=c&d', title: '' })
    expect(browser().windows.create).toHaveBeenCalledWith({
      url: 'chrome-extension://fake-extension-id/popup.html?url=https%3A%2F%2Fexample.com%2Fa%3Fb%3Dc%26d&title=',
      type: 'popup',
      width: 392,
      height: 640,
    })
  })
})

describe('shortAddress', () => {
  it('is the host and path, cut to a length that can be said', () => {
    expect(shortAddress('https://www.example.com/')).toBe('example.com')
    expect(shortAddress('https://example.com/a/b?c=d#e')).toBe('example.com/a/b')
    expect(shortAddress(`https://example.com/${'long/'.repeat(20)}`)).toHaveLength(40)
    expect(shortAddress('')).toBe('This page')
  })
})
