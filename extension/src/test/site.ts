// The listlinkedin site, for tests of the extension's pages: a mocked `fetch` that answers by
// method and path, and records what was asked.
import { vi } from 'vitest'

import { json } from './fakeBrowser'

export type Route = (init: RequestInit) => Response | Error

/** A list as /api/v2/ sends it, as far as the extension reads it. */
export const apiList = (code: string, extra: Record<string, unknown> = {}) => ({
  code,
  title: `List ${code}`,
  url: `https://lists.example.test/l/${code}`,
  visibility: 'private',
  link_count: 3,
  permissions: ['view', 'edit'],
  ...extra,
})

/**
 * Stubs `fetch` with `routes` (`'POST /api/v2/lists/'`: with or without the query). Anything
 * else answers 404. Returns the requests made, as `'METHOD /path?query'`.
 */
export function site(routes: Record<string, Route>) {
  const calls: string[] = []
  const bodies: unknown[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit) => {
      const path = url.replace('https://lists.example.test', '')
      calls.push(`${init.method} ${path}`)
      bodies.push(typeof init.body === 'string' ? JSON.parse(init.body) : undefined)
      const route =
        routes[`${init.method} ${path}`] ?? routes[`${init.method} ${path.split('?')[0]}`]
      const answer = route ? route(init) : json({ detail: 'Not found.' }, 404)
      if (answer instanceof Error) throw answer
      return answer
    }),
  )
  return { calls, bodies }
}

/** `{next: null, results}`: one page of a paginated answer. */
export const page = (results: unknown[]) => json({ next: null, results })
