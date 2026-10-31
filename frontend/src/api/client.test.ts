import { afterEach, describe, expect, it, vi } from 'vitest'

import { addLink, ApiError, errorMessage, getLinks, NetworkError, request } from '.'

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

function setCookie(value: string) {
  Object.defineProperty(document, 'cookie', { value, configurable: true, writable: true })
}

afterEach(() => {
  vi.unstubAllGlobals()
  setCookie('')
})

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

  it('reads the v2 machine code without treating it as a field error', () => {
    const error = new ApiError(409, { detail: 'Changed meanwhile.', code: 'stale_preview' })
    expect(error.code).toBe('stale_preview')
    expect(error.fieldErrors).toEqual({})
  })

  it('maps allauth errors to fields and a general message', () => {
    const error = new ApiError(400, {
      status: 400,
      errors: [
        { message: 'This password is too short.', code: 'password_too_short', param: 'password' },
        { message: 'This password is too common.', code: 'password_too_common', param: 'password' },
        { message: 'Too many attempts.', code: 'too_many_login_attempts' },
      ],
    })
    expect(error.fieldErrors).toEqual({
      password: ['This password is too short.', 'This password is too common.'],
    })
    expect(error.detail).toBe('Too many attempts.')
    expect(error.code).toBe('password_too_short')
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
    expect(init?.credentials).toBe('same-origin')
  })

  it('needs no CSRF token for owner-token requests', async () => {
    respond(201, { id: '1' })
    await addLink('CODE', 'secret', { destination_url: 'https://example.com/' })
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1)
    const headers = vi.mocked(fetch).mock.calls[0]![1]!.headers as Record<string, string>
    expect(headers['X-CSRFToken']).toBeUndefined()
  })

  it('sends the CSRF cookie back as a header on session writes', async () => {
    setCookie('other=1; csrftoken=abc123')
    respond(200, {})
    await request('/api/v2/me/', { method: 'PATCH', body: { display_name: 'Ada' } })
    const headers = vi.mocked(fetch).mock.calls[0]![1]!.headers as Record<string, string>
    expect(headers['X-CSRFToken']).toBe('abc123')
  })

  it("reads production's __Host- CSRF cookie first", async () => {
    setCookie('csrftoken=stale; __Host-csrftoken=secure123')
    respond(200, {})
    await request('/api/v2/me/', { method: 'PATCH', body: { display_name: 'Ada' } })
    const headers = vi.mocked(fetch).mock.calls[0]![1]!.headers as Record<string, string>
    expect(headers['X-CSRFToken']).toBe('secure123')
  })

  it('fetches the session first when there is no CSRF cookie yet', async () => {
    const fetchMock = vi.fn().mockImplementation(async (url: string) => {
      if (url === '/api/v2/session/') setCookie('csrftoken=fresh')
      return new Response('{}', { status: 200 })
    })
    vi.stubGlobal('fetch', fetchMock)
    await request('/_allauth/browser/v1/auth/login', { method: 'POST', body: {} })
    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      '/api/v2/session/',
      '/_allauth/browser/v1/auth/login',
    ])
    expect((fetchMock.mock.calls[1]![1].headers as Record<string, string>)['X-CSRFToken']).toBe(
      'fresh',
    )
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
