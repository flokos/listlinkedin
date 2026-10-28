import { afterEach, describe, expect, it, vi } from 'vitest'

import { addLink, ApiError, errorMessage, getLinks, NetworkError } from './api'

function respond(status: number, body: unknown, headers: Record<string, string> = {}) {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(
        new Response(body === null ? null : JSON.stringify(body), { status, headers }),
      ),
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('ApiError', () => {
  it('parses DRF field errors and picks the first as the user message', () => {
    const error = new ApiError(400, { destination_url: ['This URL is already in the list.'] })
    expect(error.fieldErrors).toEqual({ destination_url: ['This URL is already in the list.'] })
    expect(error.userMessage).toBe('This URL is already in the list.')
  })

  it('prefers DRF detail messages', () => {
    expect(new ApiError(410, { detail: 'This list has expired.' }).userMessage).toBe(
      'This list has expired.',
    )
  })

  it('falls back to a message per status', () => {
    expect(new ApiError(403, null).userMessage).toMatch(/permission/)
    expect(new ApiError(502, null).userMessage).toMatch(/our side/)
  })

  it('reads Retry-After for rate limits', () => {
    expect(new ApiError(429, null, '120').retryAfter).toBe(120)
    expect(new ApiError(429, null, null).retryAfter).toBeUndefined()
  })
})

describe('request', () => {
  it('sends the owner token as a bearer header and JSON body', async () => {
    respond(201, { id: '1' })
    await addLink('CODE', 'secret', { destination_url: 'https://example.com/' })
    const [url, init] = vi.mocked(fetch).mock.calls[0]!
    expect(url).toBe('/api/v1/lists/CODE/links/')
    expect(init?.method).toBe('POST')
    expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer secret')
    expect(init?.body).toBe('{"destination_url":"https://example.com/"}')
    expect(init?.credentials).toBe('omit')
  })

  it('loads a whole list of links in one page', async () => {
    respond(200, { count: 0, next: null, previous: null, results: [] })
    await getLinks('CODE')
    expect(vi.mocked(fetch).mock.calls[0]![0]).toBe('/api/v1/lists/CODE/links/?page_size=100')
  })

  it('throws ApiError with status and parsed body', async () => {
    respond(429, { detail: 'Request was throttled.' }, { 'Retry-After': '30' })
    const error = await getLinks('CODE').catch((e) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(429)
    expect(error.retryAfter).toBe(30)
  })

  it('wraps network failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const error = await getLinks('CODE').catch((e) => e)
    expect(error).toBeInstanceOf(NetworkError)
    expect(errorMessage(error)).toMatch(/connection/)
  })
})
