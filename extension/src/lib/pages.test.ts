import { describe, expect, it } from 'vitest'

import { browser } from '../test/fakeBrowser'
import { browserName, pageToSave, titleFrom, whyNotSaveable } from './pages'

describe('whyNotSaveable', () => {
  it('lets ordinary web pages through', () => {
    for (const url of ['https://example.com/', 'http://example.org/a?b=c#d', 'https://例え.jp/'])
      expect(whyNotSaveable(url), url).toBeNull()
  })

  it("says why for pages the site wouldn't take", () => {
    expect(whyNotSaveable(undefined)).toMatch(/no address/)
    expect(whyNotSaveable('chrome://extensions')).toMatch(/Only web pages/)
    expect(whyNotSaveable('about:blank')).toMatch(/Only web pages/)
    expect(whyNotSaveable('file:///home/me/notes.txt')).toMatch(/Only web pages/)
    expect(whyNotSaveable('https://me:secret@example.com/')).toMatch(/username or password/)
    expect(whyNotSaveable('https://lists.example.test/l/abc')).toMatch(/listlinkedin itself/)
    expect(whyNotSaveable(`https://example.com/${'x'.repeat(2100)}`)).toMatch(/too long/)
  })
})

describe('titleFrom', () => {
  it('makes one line of at most 255 characters', () => {
    expect(titleFrom('  A\n  title\t here ')).toBe('A title here')
    expect(titleFrom('x'.repeat(300))).toHaveLength(255)
    expect(titleFrom(undefined)).toBe('')
  })
})

describe('pageToSave', () => {
  it('is the active tab when the popup is opened from the toolbar', async () => {
    browser().tabs.query.mockResolvedValue([{ url: 'https://example.com/a', title: ' A page ' }])

    expect(await pageToSave('')).toEqual({ url: 'https://example.com/a', title: 'A page' })
    expect(browser().tabs.query).toHaveBeenCalledWith({ active: true, currentWindow: true })
  })

  it('is null when the browser shows no address for the tab', async () => {
    browser().tabs.query.mockResolvedValue([{ title: 'New tab' }])
    expect(await pageToSave('')).toBeNull()
  })

  it('is the address in the query when opened as a page', async () => {
    const page = await pageToSave('?url=https%3A%2F%2Fexample.com%2Fb&title=A%20link')
    expect(page).toEqual({ url: 'https://example.com/b', title: 'A link' })
    expect(browser().tabs.query).not.toHaveBeenCalled()
  })
})

describe('browserName', () => {
  it('names the browser and the system', () => {
    const cases: [string, string][] = [
      [
        'Mozilla/5.0 (X11; Linux x86_64; rv:145.0) Gecko/20100101 Firefox/145.0',
        'Firefox on Linux',
      ],
      [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
        'Chrome on Windows',
      ],
      [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0',
        'Edge on macOS',
      ],
      ['Something/1.0', 'Browser'],
    ]
    for (const [userAgent, name] of cases) expect(browserName(userAgent)).toBe(name)
  })
})
