import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ADA, json } from '../test/fakeBrowser'
import {
  addToGroup,
  byLastUse,
  createList,
  fetchGroupLists,
  fetchGroups,
  fetchLinks,
  fetchLists,
  lastUsedList,
  savePage,
  setVisibility,
} from './lists'
import {
  cacheLists,
  getCachedLists,
  getNewListVisibility,
  getRecent,
  markUsed,
  saveConnection,
} from './storage'

const apiList = (code: string, permissions = ['view', 'edit', 'settings'], extra = {}) => ({
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
        canSet: true,
      },
      expect.objectContaining({ code: 'B', canEdit: false, canSet: false }),
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
      json({
        next: null,
        results: [
          {
            code: 'G',
            title: 'Team',
            url: 'https://lists.example.test/g/G',
            visibility: 'unlisted',
            list_count: 2,
            permissions: ['view', 'edit', 'add_list'],
            extra: true,
          },
        ],
      }),
      json([apiList('A'), apiList('B', ['view'])]),
    )

    expect(await fetchGroups()).toEqual([
      {
        code: 'G',
        title: 'Team',
        url: 'https://lists.example.test/g/G',
        visibility: 'unlisted',
        listCount: 2,
        canAddList: true,
        canSet: false, // an editor of the group, not its owner
        canEdit: true,
        canDelete: false,
      },
    ])
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

    const created = await createList('New', 'key-1', 'unlisted')

    const [url, init] = fetch.mock.calls[0]!
    expect(url).toBe('https://lists.example.test/api/v2/lists/')
    expect(init).toMatchObject({ method: 'POST', body: '{"title":"New","visibility":"unlisted"}' })
    expect(init.headers).toMatchObject({ 'Idempotency-Key': 'key-1' })
    expect(created).toMatchObject({ code: 'N', title: 'New', linkCount: 0, canEdit: true })
    expect((await getCachedLists())!.map((list) => list.code)).toEqual(['N', 'A'])
    // The answer is offered again the next time a list is made here.
    expect(await getNewListVisibility()).toBe('unlisted')
  })
})

describe('the list used last', () => {
  const summaries = async (...codes: string[]) => {
    answers(json({ next: null, results: codes.map((code) => apiList(code)) }))
    return fetchLists()
  }

  it('puts the lists saved to last first, newest first, and leaves the rest in order', async () => {
    const lists = await summaries('A', 'B', 'C', 'D')
    expect(byLastUse(lists, ['C', 'gone', 'B']).map((list) => list.code)).toEqual([
      'C',
      'B',
      'A',
      'D',
    ])
    expect(lists.map((list) => list.code)).toEqual(['A', 'B', 'C', 'D']) // not sorted in place
  })

  it('is the one saved to last, and no other when that one is gone', async () => {
    expect(await lastUsedList()).toBeNull() // nothing saved from this browser yet
    await summaries('A', 'B')
    expect(await lastUsedList()).toBeNull() // lists, but none used here

    await markUsed('B')
    expect((await lastUsedList())?.code).toBe('B')

    await markUsed('deleted-since')
    expect(await lastUsedList()).toBeNull() // never the next best
  })
})

describe('links', () => {
  it("reads a list's links as the site shows them", async () => {
    const fetch = answers(
      json({
        next: null,
        results: [
          {
            id: 'l1',
            destination_url: 'https://example.com/article',
            short_url: 'https://lists.example.test/r/abc',
            title: null,
            display: { title: 'Fetched title', site_name: 'Example' },
          },
        ],
      }),
    )

    expect(await fetchLinks('A B')).toEqual([
      {
        id: 'l1',
        title: 'Fetched title',
        url: 'https://example.com/article',
        site: 'Example',
        shortUrl: 'https://lists.example.test/r/abc',
      },
    ])
    expect(urls(fetch)).toEqual([
      'https://lists.example.test/api/v2/lists/A%20B/links/?page_size=100&page=1',
    ])
  })
})

describe('sharing', () => {
  it('changes who can open a list and keeps what it learned', async () => {
    await cacheLists([
      {
        code: 'A',
        title: 'List A',
        url: 'u',
        visibility: 'private',
        linkCount: 3,
        canEdit: true,
        canSet: true,
      },
    ])
    const fetch = answers(json(apiList('A', undefined, { visibility: 'unlisted' })))

    const list = await setVisibility('A', 'unlisted')

    const [url, init] = fetch.mock.calls[0]!
    expect(url).toBe('https://lists.example.test/api/v2/lists/A/')
    expect(init).toMatchObject({ method: 'PATCH', body: '{"visibility":"unlisted"}' })
    expect(list.visibility).toBe('unlisted')
    expect((await getCachedLists())![0]!.visibility).toBe('unlisted')
  })

  it("leaves what is kept alone when the server won't change it", async () => {
    await cacheLists([
      {
        code: 'A',
        title: 'List A',
        url: 'u',
        visibility: 'private',
        linkCount: 3,
        canEdit: true,
        canSet: true,
      },
    ])
    answers(json({ visibility: ['Verify your email address to make a list public.'] }, 400))

    await expect(setVisibility('A', 'public')).rejects.toMatchObject({
      userMessage: 'Verify your email address to make a list public.',
    })
    expect((await getCachedLists())![0]!.visibility).toBe('private')
  })

  it('adds a list to a group, and reports a refusal without failing', async () => {
    const fetch = answers(
      json(apiList('A'), 201),
      json({ detail: 'This list is already in the group.', code: 'duplicate_list' }, 409),
      json({ detail: "You can't share this list.", code: 'cannot_share_list' }, 403),
      json({ detail: 'Not found.' }, 404),
    )

    expect(await addToGroup('G', 'A')).toEqual({ added: true })
    const [url, init] = fetch.mock.calls[0]!
    expect(url).toBe('https://lists.example.test/api/v2/groups/G/lists/')
    expect(init).toMatchObject({ method: 'POST', body: '{"list":"A"}' })

    expect(await addToGroup('G', 'A')).toEqual({
      added: false,
      reason: 'This list is already in the group.',
    })
    expect(await addToGroup('G', 'A')).toEqual({
      added: false,
      reason: "You can't share this list.",
    })
    await expect(addToGroup('G', 'A')).rejects.toMatchObject({ status: 404 })
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
