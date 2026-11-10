import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ADA, json } from '../test/fakeBrowser'
import { createList, fetchGroupLists, fetchGroups, fetchLists, savePage } from './lists'
import { getCachedLists, getRecent, saveConnection } from './storage'

const apiList = (code: string, permissions = ['view', 'edit'], extra = {}) => ({
  id: `id-${code}`,
  code,
  title: `List ${code}`,
  url: `https://lists.example.test/l/${code}`,
  visibility: 'private',
  link_count: 3,
  permissions,
  ...extra,
})

const answers = (...responses: (Response | Error)[]) => {
  const fetch = vi.fn<(url: string, init: RequestInit) => Promise<Response>>(async () => {
    const next = responses.shift()!
    if (next instanceof Error) throw next
    return next
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}
const urls = (fetch: ReturnType<typeof answers>) => fetch.mock.calls.map(([url]) => url)

beforeEach(() => saveConnection(ADA))

describe('fetchLists', () => {
  it('reads every page, keeps what choosing needs, and caches it', async () => {
    const fetch = answers(
      json({ next: 'https://elsewhere.example/api/v2/lists/?page=2', results: [apiList('A')] }),
      json({ next: null, results: [apiList('B', ['view'])] }),
    )

    const lists = await fetchLists()

    // Pages are asked for by number: `next` is never followed as an address.
    expect(urls(fetch)).toEqual([
      'https://lists.example.test/api/v2/lists/?page_size=100&page=1',
      'https://lists.example.test/api/v2/lists/?page_size=100&page=2',
    ])
    expect(lists).toEqual([
      {
        code: 'A',
        title: 'List A',
        url: 'https://lists.example.test/l/A',
        visibility: 'private',
        linkCount: 3,
        canEdit: true,
      },
      expect.objectContaining({ code: 'B', canEdit: false }),
    ])
    expect(await getCachedLists()).toEqual(lists)
  })

  it('stops after five pages', async () => {
    const page = () => json({ next: 'more', results: [apiList('A')] })
    const fetch = answers(page(), page(), page(), page(), page(), page())
    expect(await fetchLists()).toHaveLength(5)
    expect(fetch).toHaveBeenCalledTimes(5)
  })
})

describe('groups', () => {
  it('lists the groups and the lists a group shows', async () => {
    const fetch = answers(
      json({ next: null, results: [{ code: 'G', title: 'Team', list_count: 2, extra: true }] }),
      json([apiList('A'), apiList('B', ['view'])]),
    )

    expect(await fetchGroups()).toEqual([{ code: 'G', title: 'Team', listCount: 2 }])
    expect((await fetchGroupLists('G')).map((list) => [list.code, list.canEdit])).toEqual([
      ['A', true],
      ['B', false],
    ])
    expect(urls(fetch)[1]).toBe('https://lists.example.test/api/v2/groups/G/lists/')
  })
})

describe('createList', () => {
  it('creates a list once per key and puts it first in the cache', async () => {
    answers(json({ next: null, results: [apiList('A')] }))
    await fetchLists()
    const fetch = answers(
      json(apiList('N', ['view', 'edit'], { title: 'New', link_count: 0 }), 201),
    )

    const created = await createList('New', 'key-1')

    const [url, init] = fetch.mock.calls[0]!
    expect(url).toBe('https://lists.example.test/api/v2/lists/')
    expect(init).toMatchObject({ method: 'POST', body: '{"title":"New"}' })
    expect(init.headers).toMatchObject({ 'Idempotency-Key': 'key-1' })
    expect(created).toMatchObject({ code: 'N', title: 'New', linkCount: 0, canEdit: true })
    expect((await getCachedLists())!.map((list) => list.code)).toEqual(['N', 'A'])
  })
})

describe('savePage', () => {
  const page = { url: 'https://example.com/article', title: '  An article  ' }

  it('adds the page with its title and remembers the list', async () => {
    const fetch = answers(
      json({ id: 'link-1', short_url: 'https://lists.example.test/r/abc' }, 201),
    )

    const outcome = await savePage('A', page, 'key-1')

    const [url, init] = fetch.mock.calls[0]!
    expect(url).toBe('https://lists.example.test/api/v2/lists/A/links/')
    expect(JSON.parse(init.body as string)).toEqual({
      destination_url: 'https://example.com/article',
      title: 'An article',
    })
    expect(init.headers).toMatchObject({ 'Idempotency-Key': 'key-1', 'X-Session-Token': ADA.token })
    expect(outcome).toEqual({
      saved: true,
      link: { id: 'link-1', short_url: 'https://lists.example.test/r/abc' },
    })
    expect(await getRecent()).toEqual(['A'])
  })

  it('sends no title rather than an empty one', async () => {
    const fetch = answers(json({ id: 'link-1', short_url: null }, 201))
    await savePage('A', { url: page.url, title: '   ' }, 'key-1')
    expect(JSON.parse(fetch.mock.calls[0]![1].body as string).title).toBeNull()
  })

  it("reports why the server didn't take the page, without failing", async () => {
    answers(json({ destination_url: ['This URL is already in the list.'], code: 'invalid' }, 400))
    expect(await savePage('A', page, 'key-1')).toEqual({
      saved: false,
      reason: 'This URL is already in the list.',
    })
    expect(await getRecent()).toEqual([])
  })

  it('throws for anything that is a failure', async () => {
    answers(json({ detail: "You can't change this list." }, 403))
    await expect(savePage('A', page, 'key-1')).rejects.toMatchObject({ status: 403 })
  })

  it('keeps the eight lists used last, newest first', async () => {
    for (const code of ['A', 'B', 'A', 'C', 'D', 'E', 'F', 'G', 'H', 'I']) {
      answers(json({ id: 'x', short_url: null }, 201))
      await savePage(code, page, `key-${code}`)
    }
    expect(await getRecent()).toEqual(['I', 'H', 'G', 'F', 'E', 'D', 'C', 'A'])
  })
})
