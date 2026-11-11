import { describe, expect, it } from 'vitest'

import { browser } from '../test/fakeBrowser'
import { historyPages, openTabs, saveable } from './sources'

describe('saveable', () => {
  it('keeps what the site would take, each address once, in order', () => {
    expect(
      saveable([
        { url: 'https://example.com/a', title: '  A   page ' },
        { url: 'about:blank', title: 'Blank' },
        { url: 'https://lists.example.test/lists', title: 'The site itself' },
        { title: 'No address' },
        { url: 'https://example.com/a', title: 'The same again' },
        { url: 'http://example.org/', title: undefined },
      ]),
    ).toEqual([
      { url: 'https://example.com/a', title: 'A page' },
      { url: 'http://example.org/', title: '' },
    ])
  })
})

describe('openTabs', () => {
  it('reads the tabs of every ordinary window and leaves private ones out', async () => {
    browser().tabs.query.mockResolvedValue([
      { url: 'https://example.com/a', title: 'A' },
      { url: 'https://example.com/secret', title: 'Private', incognito: true },
      { url: 'chrome://settings/', title: 'Settings' },
      { url: 'https://example.com/b', title: 'B' },
    ])

    expect(await openTabs()).toEqual([
      { url: 'https://example.com/a', title: 'A' },
      { url: 'https://example.com/b', title: 'B' },
    ])
    expect(browser().tabs.query).toHaveBeenCalledWith({}) // every window, not only this one
  })
})

describe('historyPages', () => {
  it('asks the browser for all of the history, and shows the latest visit first', async () => {
    browser().history.search.mockResolvedValue([
      { url: 'https://example.com/old', title: 'Old', lastVisitTime: 100 },
      { url: 'https://example.com/new', title: 'New', lastVisitTime: 300 },
      { url: 'file:///home/me/notes.txt', title: 'Notes', lastVisitTime: 250 },
      { url: 'https://example.com/mid', title: 'Mid', lastVisitTime: 200 },
    ])

    const pages = await historyPages('  exam ')

    expect(pages.map((page) => page.title)).toEqual(['New', 'Mid', 'Old'])
    expect(browser().history.search).toHaveBeenCalledWith({
      text: 'exam',
      startTime: 0, // not only the last day, the browser's default
      maxResults: 200,
    })
  })
})
