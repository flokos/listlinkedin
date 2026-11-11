// A stand-in for the WebExtensions API in unit tests: storage that behaves like the real one
// (copies values, reports changes), events that tests can fire, and spies for the rest.
import { vi } from 'vitest'

type Changes = Record<string, { oldValue?: unknown; newValue?: unknown }>

function event<L extends (...args: never[]) => unknown>() {
  const listeners = new Set<L>()
  return {
    addListener: (listener: L) => void listeners.add(listener),
    removeListener: (listener: L) => void listeners.delete(listener),
    /** Calls every listener, as the browser would, and returns what they returned. */
    fire: (...args: Parameters<L>) => [...listeners].map((listener) => listener(...args)),
  }
}

export interface Sender {
  id?: string
  url?: string
  frameId?: number
  tab?: { id: number }
}

export function fakeBrowser() {
  const onChanged = event<(changes: Changes, area: string) => void>()
  const area = (name: string) => {
    const data = new Map<string, unknown>()
    return {
      data,
      get: vi.fn(async (keys?: string | string[] | null) => {
        const wanted = keys == null ? [...data.keys()] : typeof keys === 'string' ? [keys] : keys
        return Object.fromEntries(
          wanted.filter((key) => data.has(key)).map((key) => [key, structuredClone(data.get(key))]),
        )
      }),
      set: vi.fn(async (values: Record<string, unknown>) => {
        const changes: Changes = {}
        for (const [key, value] of Object.entries(values)) {
          changes[key] = { oldValue: data.get(key), newValue: structuredClone(value) }
          data.set(key, structuredClone(value))
        }
        onChanged.fire(changes, name)
      }),
      remove: vi.fn(async (keys: string | string[]) => {
        const changes: Changes = {}
        for (const key of typeof keys === 'string' ? [keys] : keys) {
          if (!data.has(key)) continue
          changes[key] = { oldValue: data.get(key) }
          data.delete(key)
        }
        if (Object.keys(changes).length) onChanged.fire(changes, name)
      }),
    }
  }
  return {
    runtime: {
      id: 'fake-extension-id',
      getURL: (path: string) => `chrome-extension://fake-extension-id/${path}`,
      sendMessage: vi.fn<(message: unknown) => Promise<unknown>>(async () => undefined),
      openOptionsPage: vi.fn(async () => {}),
      onInstalled: event<(details: { reason: string }) => void>(),
      onMessage:
        event<(message: unknown, sender: Sender, respond: (reply: unknown) => void) => boolean>(),
    },
    storage: { local: area('local'), session: area('session'), onChanged },
    tabs: {
      create: vi.fn(async (options: { url: string }) => ({ id: 1, ...options })),
      query: vi.fn<(query: unknown) => Promise<{ url?: string; title?: string }[]>>(async () => []),
    },
    permissions: {
      contains: vi.fn<(wanted: { origins: string[] }) => Promise<boolean>>(async () => true),
      request: vi.fn<(wanted: { origins: string[] }) => Promise<boolean>>(async () => true),
    },
  }
}

export type FakeBrowser = ReturnType<typeof fakeBrowser>

let current: FakeBrowser

/** Replaces `chrome` with a new fake and returns it. */
export function installFakeBrowser(): FakeBrowser {
  current = fakeBrowser()
  const scope = globalThis as unknown as { chrome?: unknown; browser?: unknown }
  scope.chrome = current
  delete scope.browser
  return current
}

/** The fake this test runs against (src/test/setup.ts installs one before each test). */
export const browser = (): FakeBrowser => current

/** A connection as storage holds it. */
export const ADA = {
  id: '0b0c7f0e-7c1b-4a55-9d0e-3f6a5a0d9a11',
  token: 'session-token-of-ada',
  name: 'Firefox on Linux',
  email: 'ada@example.com',
}

/** A JSON answer from the site, for a mocked `fetch`. */
export const json = (body: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(body === null ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  })
