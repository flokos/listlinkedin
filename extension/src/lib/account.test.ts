import { describe, expect, it, vi } from 'vitest'

import { ADA, browser, json } from '../test/fakeBrowser'
import { asAccount, disconnect, Disconnected } from './account'
import { NetworkError } from './api'
import { cacheLists, getCachedLists, getConnection, markUsed, saveConnection } from './storage'

const answers = (...responses: (Response | Error)[]) => {
  const fetch = vi.fn<(url: string, init: RequestInit) => Promise<Response>>(async () => {
    const next = responses.shift()!
    if (next instanceof Error) throw next
    return next
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

describe('asAccount', () => {
  it("calls the API with the connection's token", async () => {
    await saveConnection(ADA)
    const fetch = answers(json({ email: ADA.email }))

    expect(await asAccount('/api/v2/me/')).toEqual({ email: ADA.email })
    expect(fetch.mock.calls[0]![1].headers).toMatchObject({ 'X-Session-Token': ADA.token })
  })

  it("doesn't call the site when nothing is connected", async () => {
    const fetch = answers()
    await expect(asAccount('/api/v2/me/')).rejects.toBeInstanceOf(Disconnected)
    expect(fetch).not.toHaveBeenCalled()
  })

  it('forgets the account when the site says the connection is over', async () => {
    await saveConnection(ADA)
    await cacheLists([])
    await markUsed('L1')
    answers(json({ detail: 'Sign in.', code: 'not_authenticated' }, 401))

    await expect(asAccount('/api/v2/lists/')).rejects.toBeInstanceOf(Disconnected)

    expect(await getConnection()).toBeNull()
    expect(await getCachedLists()).toBeNull()
    expect(browser().storage.local.data.size).toBe(0)
  })

  it('keeps a connection made while the old request was on its way', async () => {
    await saveConnection(ADA)
    const newer = { ...ADA, token: 'a-newer-token' }
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        await saveConnection(newer)
        return json({ detail: 'Sign in.' }, 401)
      }),
    )

    await expect(asAccount('/api/v2/lists/')).rejects.toBeInstanceOf(Disconnected)
    expect(await getConnection()).toEqual(newer)
  })

  it('keeps the account on any other failure', async () => {
    await saveConnection(ADA)
    answers(json({ detail: 'No.' }, 403), new TypeError('Failed to fetch'))

    await expect(asAccount('/x')).rejects.toMatchObject({ status: 403 })
    await expect(asAccount('/x')).rejects.toBeInstanceOf(NetworkError)
    expect(await getConnection()).toEqual(ADA)
  })
})

describe('disconnect', () => {
  it('ends the session on the site, then forgets the account', async () => {
    await saveConnection(ADA)
    const fetch = answers(json(null, 204))

    await disconnect()

    const [url, init] = fetch.mock.calls[0]!
    expect(url).toBe(`https://lists.example.test/api/v2/me/browsers/${ADA.id}/`)
    expect(init).toMatchObject({ method: 'DELETE', credentials: 'omit' })
    expect(init.headers).toMatchObject({ 'X-Session-Token': ADA.token })
    expect(await getConnection()).toBeNull()
  })

  it('forgets the account even when the site is unreachable or already ended it', async () => {
    for (const answer of [new TypeError('Failed to fetch'), json({ detail: 'Sign in.' }, 401)]) {
      await saveConnection(ADA)
      answers(answer)
      await disconnect()
      expect(await getConnection()).toBeNull()
    }
  })

  it('does nothing when nothing is connected', async () => {
    const fetch = answers()
    await disconnect()
    expect(fetch).not.toHaveBeenCalled()
  })
})
