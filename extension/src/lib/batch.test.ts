import { beforeEach, describe, expect, it } from 'vitest'

import { ADA, json } from '../test/fakeBrowser'
import { site } from '../test/site'
import { Disconnected } from './account'
import { BatchStopped, describe as say, PART_BYTES, parts, saveMany } from './batch'
import { getRecent, saveConnection } from './storage'

const BATCH = 'POST /api/v2/lists/A/links/batch/'
const pages = (n: number, pad = '') =>
  Array.from({ length: n }, (_, i) => ({
    url: `https://example.com/${pad}${i}`,
    title: `Page ${i}`,
  }))

beforeEach(() => saveConnection(ADA))

describe('parts', () => {
  it('keeps a small selection in one part', () => {
    expect(parts(pages(40))).toHaveLength(1)
    expect(parts([])).toEqual([])
  })

  it('never sends more than a hundred links, or more bytes than the site takes, at once', () => {
    expect(parts(pages(250)).map((part) => part.length)).toEqual([100, 100, 50])

    const long = parts(pages(60, 'x'.repeat(600))) // about 40 KB in all
    expect(long.length).toBeGreaterThan(3)
    for (const part of long) {
      const body = JSON.stringify({
        links: part.map((page) => ({ destination_url: page.url, title: page.title })),
      })
      expect(new TextEncoder().encode(body).length).toBeLessThan(PART_BYTES + 200)
    }
    expect(long.flat()).toHaveLength(60) // nothing lost, and in order
    expect(long.flat()[59]!.title).toBe('Page 59')
  })

  it('counts bytes, not characters', () => {
    const greek = pages(30).map((page) => ({ ...page, title: 'λίστα '.repeat(40) }))
    expect(parts(greek).length).toBeGreaterThan(1)
  })
})

describe('saveMany', () => {
  it('sends the pages as the site wants them and adds up its answers', async () => {
    const { calls, bodies } = site({
      [BATCH]: () =>
        json({
          added: [{ id: '1' }, { id: '2' }],
          skipped: [
            { index: 1, reason: 'duplicate' },
            { index: 3, reason: 'invalid' },
            { index: 4, reason: 'list_full' },
          ],
        }),
    })

    const result = await saveMany('A', [
      ...pages(4),
      { url: 'https://example.com/untitled', title: '' },
    ])

    expect(calls).toEqual([BATCH])
    expect((bodies[0] as { links: unknown[] }).links.at(0)).toEqual({
      destination_url: 'https://example.com/0',
      title: 'Page 0',
    })
    expect((bodies[0] as { links: unknown[] }).links.at(-1)).toEqual({
      destination_url: 'https://example.com/untitled',
      title: null, // none: the site shows the page's own
    })
    expect(result).toEqual({ saved: 2, duplicate: 1, invalid: 1, full: 1, unsent: 0 })
    expect(await getRecent()).toEqual(['A']) // the list is the one used last now
  })

  it('sends a long selection in parts, one change each', async () => {
    const { calls } = site({ [BATCH]: () => json({ added: [{}], skipped: [] }) })
    const result = await saveMany('A', pages(230))
    expect(calls).toHaveLength(3)
    expect(result).toMatchObject({ saved: 3, unsent: 0 })
  })

  it('stops at a part that fails and says what was done until then', async () => {
    let asked = 0
    site({
      [BATCH]: () =>
        (asked += 1) === 1
          ? json({ added: Array(100).fill({}), skipped: [] })
          : json({ detail: 'Slow down.' }, 429, { 'Retry-After': '120' }),
    })

    const stopped = await saveMany('A', pages(230)).catch((error: unknown) => error)

    expect(stopped).toBeInstanceOf(BatchStopped)
    expect((stopped as BatchStopped).result).toEqual({
      saved: 100,
      duplicate: 0,
      invalid: 0,
      full: 0,
      unsent: 130,
    })
    expect(asked).toBe(2) // the third part was never sent
    expect(await getRecent()).toEqual(['A'])
  })

  it('reports a connection that is over', async () => {
    site({ [BATCH]: () => json({ detail: 'Sign in.' }, 401) })
    const stopped = (await saveMany('A', pages(2)).catch((error: unknown) => error)) as BatchStopped
    expect(stopped.reason).toBeInstanceOf(Disconnected)
    expect(await getRecent()).toEqual([])
  })
})

describe('describe', () => {
  it('says the result in a sentence, leaving out what did not happen', () => {
    expect(say({ saved: 37, duplicate: 3, invalid: 0, full: 5, unsent: 0 })).toBe(
      "37 pages saved, 3 were already there, 5 didn't fit (a list holds 100 links).",
    )
    expect(say({ saved: 1, duplicate: 1, invalid: 1, full: 0, unsent: 2 })).toBe(
      "1 page saved, 1 was already there, 1 address wasn't accepted, 2 weren't sent.",
    )
    expect(say({ saved: 0, duplicate: 0, invalid: 0, full: 0, unsent: 0 })).toBe('0 pages saved.')
  })
})
