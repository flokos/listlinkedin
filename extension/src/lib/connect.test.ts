// @vitest-environment node
import { describe, expect, it, vi } from 'vitest'

import { browser, json } from '../test/fakeBrowser'
import { finishConnect, startConnect, startedHere } from './connect'
import { challengeFor } from './pkce'
import { getConnection, getPending } from './storage'

const answers = (response: Response | Error) => {
  const fetch = vi.fn<(url: string, init: RequestInit) => Promise<Response>>(async () => {
    if (response instanceof Error) throw response
    return response
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

const connected = {
  id: 'browser-1',
  name: 'Firefox on Linux',
  session_token: 'the-session-token',
  user: { id: 'u1', email: 'ada@example.com', display_name: 'Ada' },
}

describe('startConnect', () => {
  it('keeps a new PKCE pair and opens the Connect page with only its challenge', async () => {
    await startConnect()

    const pending = (await getPending())!
    expect(pending.challenge).toBe(await challengeFor(pending.verifier))
    const url = new URL(browser().tabs.create.mock.calls[0]![0].url)
    expect(url.origin + url.pathname).toBe('https://lists.example.test/connect-browser')
    expect(url.searchParams.get('challenge')).toBe(pending.challenge)
    expect(url.searchParams.get('name')).toBeTruthy()
    expect(url.href).not.toContain(pending.verifier)
    // The verifier lives for this browser session only: never written to disk.
    expect(browser().storage.local.data.size).toBe(0)
  })
})

describe('startedHere', () => {
  it('is true only for the request this extension started, for half an hour', async () => {
    await startConnect()
    const { challenge } = (await getPending())!

    expect(await startedHere(challenge)).toBe(true)
    expect(await startedHere('x'.repeat(43))).toBe(false)

    const later = vi.spyOn(Date, 'now').mockReturnValue(Date.now() + 31 * 60_000)
    expect(await startedHere(challenge)).toBe(false)
    later.mockRestore()
  })

  it('is false when nothing was started', async () => {
    expect(await startedHere('c'.repeat(43))).toBe(false)
  })
})

describe('finishConnect', () => {
  it('exchanges the code with the verifier and keeps the session token', async () => {
    await startConnect()
    const pending = (await getPending())!
    const fetch = answers(json(connected, 201))

    await finishConnect(pending.challenge, 'the-code')

    const [url, init] = fetch.mock.calls[0]!
    expect(url).toBe('https://lists.example.test/api/v2/browsers/connect/')
    expect(init).toMatchObject({ method: 'POST', credentials: 'omit' })
    expect(JSON.parse(init.body as string)).toEqual({
      code: 'the-code',
      verifier: pending.verifier,
    })
    expect(init.headers).not.toHaveProperty('X-Session-Token')
    expect(await getConnection()).toEqual({
      id: 'browser-1',
      token: 'the-session-token',
      name: 'Firefox on Linux',
      email: 'ada@example.com',
    })
    expect(await getPending()).toBeNull()
  })

  it("refuses a code for a request it didn't start, without calling the site", async () => {
    const fetch = answers(json(connected, 201))
    await expect(finishConnect('c'.repeat(43), 'a-code')).rejects.toThrow(/expired/)
    expect(fetch).not.toHaveBeenCalled()
    expect(await getConnection()).toBeNull()
  })

  it("passes on the site's refusal and gives the request up", async () => {
    await startConnect()
    const { challenge } = (await getPending())!
    answers(json({ detail: "This code isn't valid any more.", code: 'invalid_code' }, 400))

    await expect(finishConnect(challenge, 'used-code')).rejects.toThrow(
      "This code isn't valid any more.",
    )
    expect(await getPending()).toBeNull()
    expect(await getConnection()).toBeNull()
  })

  it('keeps the request open when the site could not be reached', async () => {
    await startConnect()
    const { challenge } = (await getPending())!
    answers(new TypeError('Failed to fetch'))

    await expect(finishConnect(challenge, 'the-code')).rejects.toThrow(/Couldn't reach/)
    expect(await startedHere(challenge)).toBe(true)
  })
})
