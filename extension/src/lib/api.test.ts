import { describe, expect, it, vi } from 'vitest'

import { json } from '../test/fakeBrowser'
import { ApiError, errorMessage, NetworkError, request } from './api'

const fetchWith = (response: Response | Error) => {
  const fetch = vi.fn<(url: string, init: RequestInit) => Promise<Response>>(async () => {
    if (response instanceof Error) throw response
    return response
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

describe('request', () => {
  it("calls the site with the token and never with the site's cookies", async () => {
    const fetch = fetchWith(json({ ok: true }))

    const data = await request('/api/v2/lists/', {
      method: 'POST',
      body: { title: 'Reading' },
      token: 'the-token',
      idempotencyKey: 'a-key',
    })

    expect(data).toEqual({ ok: true })
    const [url, init] = fetch.mock.calls[0]!
    expect(url).toBe('https://lists.example.test/api/v2/lists/')
    expect(init).toMatchObject({
      method: 'POST',
      body: '{"title":"Reading"}',
      credentials: 'omit',
      cache: 'no-store',
      referrerPolicy: 'no-referrer',
    })
    expect(init.headers).toEqual({
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-Session-Token': 'the-token',
      'Idempotency-Key': 'a-key',
    })
  })

  it('sends no token header without a token, and no body on a GET', async () => {
    const fetch = fetchWith(json({ user: null }))
    await request('/api/v2/session/')
    const init = fetch.mock.calls[0]![1]
    expect(init.headers).toEqual({ Accept: 'application/json' })
    expect(init.body).toBeUndefined()
    expect(init.method).toBe('GET')
  })

  it('answers null for 204', async () => {
    fetchWith(json(null, 204))
    expect(await request('/api/v2/me/browsers/1/', { method: 'DELETE' })).toBeNull()
  })

  it("throws what the server said, in the server's words", async () => {
    fetchWith(json({ destination_url: ['This URL is already in the list.'], code: 'invalid' }, 400))
    const error = await request('/x').catch((caught: unknown) => caught)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      status: 400,
      code: 'invalid',
      fieldErrors: { destination_url: ['This URL is already in the list.'] },
      userMessage: 'This URL is already in the list.',
    })

    fetchWith(json({ detail: "This code isn't valid any more.", code: 'invalid_code' }, 400))
    expect(errorMessage(await request('/x').catch((e: unknown) => e))).toBe(
      "This code isn't valid any more.",
    )
    // A bare list of messages, as for a full list.
    fetchWith(json(['A list can contain at most 100 links.'], 400))
    expect(errorMessage(await request('/x').catch((e: unknown) => e))).toBe(
      'A list can contain at most 100 links.',
    )
  })

  it('says how long to wait when rate limited', async () => {
    fetchWith(json({ detail: 'Request was throttled.' }, 429, { 'Retry-After': '1500' }))
    const error = (await request('/x').catch((e: unknown) => e)) as ApiError
    expect(error.retryAfter).toBe(1500)
    expect(error.userMessage).toBe('Too many requests. Try again in 25 minutes.')
    fetchWith(json({ detail: 'Request was throttled.' }, 429))
    expect(errorMessage(await request('/x').catch((e: unknown) => e))).toBe(
      'Too many requests. Wait a moment and try again.',
    )
  })

  it('falls back to a plain sentence when the body says nothing', async () => {
    for (const [status, text] of [
      [403, "You can't change this list."],
      [404, 'This list no longer exists.'],
      [500, 'Something went wrong at listlinkedin. Try again in a moment.'],
    ] as const) {
      fetchWith(new Response('<html>', { status }))
      expect(errorMessage(await request('/x').catch((e: unknown) => e))).toBe(text)
    }
  })

  it('tells a failure to reach the site from a refusal', async () => {
    fetchWith(new TypeError('Failed to fetch'))
    const error = await request('/x').catch((caught: unknown) => caught)
    expect(error).toBeInstanceOf(NetworkError)
    expect(errorMessage(error)).toMatch(/Couldn't reach listlinkedin/)
  })

  it('lets an aborted request through as an abort', async () => {
    const aborted = new DOMException('Aborted', 'AbortError')
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw aborted
      }),
    )
    await expect(request('/x')).rejects.toBe(aborted)
  })
})
