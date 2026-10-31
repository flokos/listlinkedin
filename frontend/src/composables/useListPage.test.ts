import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { effectScope, ref } from 'vue'

const api = vi.hoisted(() => {
  class ApiError extends Error {
    constructor(
      readonly status: number,
      readonly body: unknown,
    ) {
      super(`API ${status}`)
    }
  }
  return {
    ApiError,
    getSession: vi.fn().mockResolvedValue(null),
    getListDetail: vi.fn(),
    listLinks: vi.fn(),
    reorderLinks: vi.fn(),
  }
})
vi.mock('../api', () => api)

const link = (id: string) => ({ id, title: id, destination_url: `https://${id}.example/` })
const order = (links: { id: string }[]) => links.map((l) => l.id).join('')

// The page runs in a scope, as in a component: its polling timer is cleared when it ends.
let scope = effectScope()
afterEach(() => scope.stop())

async function page(ids = 'abcd') {
  vi.resetModules()
  const { useListPage } = await import('./useListPage')
  api.getListDetail.mockResolvedValue({ code: 'L', permissions: ['view', 'edit'], legacy: false })
  api.listLinks.mockResolvedValue({ results: [...ids].map(link) })
  scope = effectScope()
  const listPage = scope.run(() => useListPage(ref('L')))!
  await flushPromises()
  return listPage
}

/** A promise the test resolves or rejects when it chooses. */
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (error: unknown) => void
  const promise = new Promise<T>((res, rej) => ((resolve = res), (reject = rej)))
  return { promise, resolve, reject }
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
})

describe('useListPage moves', () => {
  it('shows a move at once, then takes the order the server answers with', async () => {
    const { links, moveLink } = await page()
    const answer = deferred<unknown[]>()
    api.reorderLinks.mockReturnValue(answer.promise)

    const done = moveLink('a', 2)
    expect(order(links.value)).toBe('bcad') // before the server answers
    expect(api.reorderLinks).toHaveBeenCalledWith('L', 'a', 2, expect.any(Function))

    answer.resolve([...'bcaed'].map(link)) // someone else added "e" meanwhile
    await done
    expect(order(links.value)).toBe('bcaed')
  })

  it('applies only the latest answer when moves overlap', async () => {
    const { links, moveLink } = await page()
    const first = deferred<unknown[]>()
    const second = deferred<unknown[]>()
    api.reorderLinks.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)

    const one = moveLink('a', 3) // bcda
    const two = moveLink('b', 3) // cdab
    expect(order(links.value)).toBe('cdab')
    second.resolve([...'cdab'].map(link))
    first.resolve([...'bcda'].map(link)) // late: describes the order before the second move
    await Promise.all([one, two])
    expect(order(links.value)).toBe('cdab')
  })

  it('reloads the server order when a move fails', async () => {
    const { links, moveLink } = await page()
    api.reorderLinks.mockRejectedValue(new api.ApiError(404, {}))
    await expect(moveLink('a', 1)).rejects.toBeInstanceOf(api.ApiError)
    await flushPromises()
    expect(api.listLinks).toHaveBeenCalledTimes(2) // loaded again
    expect(order(links.value)).toBe('abcd')
  })

  it('ignores moves to the same place', async () => {
    const { moveLink } = await page()
    await moveLink('b', 1)
    expect(api.reorderLinks).not.toHaveBeenCalled()
  })
})
