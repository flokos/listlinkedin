// What the extension keeps in the browser.
//
// `storage.local` survives restarts: the connection (with its session token), and what makes
// the popup open at once (the account's lists, and the ones used last).
// `storage.session` lasts until the browser closes and is never written to disk: the secret of
// a connection that is being made.
//
// Neither is readable by web pages or by the content script.
import { ext } from './ext'

export interface Connection {
  /** The connection's id on the site, for disconnecting. */
  id: string
  /** The session token, sent as X-Session-Token to the site and nowhere else. Never logged. */
  token: string
  /** What the site calls this browser, e.g. "Firefox on Linux". */
  name: string
  /** Whose account it is. */
  email: string
}

/** A connection being made: the PKCE pair whose verifier only this extension knows. */
export interface PendingConnect {
  challenge: string
  verifier: string
  startedAt: number
}

export type Visibility = 'private' | 'unlisted' | 'public'

/** A list of the account's, as much as choosing one needs. */
export interface ListSummary {
  code: string
  title: string
  /** Its page on the site. */
  url: string
  visibility: Visibility
  linkCount: number
  /** The server's policy says this account may add links. */
  canEdit: boolean
}

interface Local {
  connection?: Connection
  lists?: ListSummary[]
  /** Codes of the lists saved to last, newest first. */
  recent?: string[]
}

const RECENT = 8

async function read<K extends keyof Local>(key: K): Promise<Local[K]> {
  return ((await ext().storage.local.get(key)) as Local)[key]
}

const write = (values: Partial<Local>) => ext().storage.local.set(values)

export const getConnection = async (): Promise<Connection | null> =>
  (await read('connection')) ?? null

export const saveConnection = (connection: Connection) => write({ connection })

/** Forgets the account: its token, and everything kept about it. */
export async function forgetAccount(): Promise<void> {
  await ext().storage.local.remove(['connection', 'lists', 'recent'] satisfies (keyof Local)[])
}

/** Calls `listener` whenever this browser gets connected or disconnected, in any page. */
export function onConnectionChange(listener: (connection: Connection | null) => void): () => void {
  const changed = (changes: Record<string, chrome.storage.StorageChange>, area: string) => {
    if (area === 'local' && 'connection' in changes)
      listener((changes.connection!.newValue as Connection | undefined) ?? null)
  }
  ext().storage.onChanged.addListener(changed)
  return () => ext().storage.onChanged.removeListener(changed)
}

export const getCachedLists = async (): Promise<ListSummary[] | null> =>
  (await read('lists')) ?? null

export const cacheLists = (lists: ListSummary[]) => write({ lists })

export const getRecent = async (): Promise<string[]> => (await read('recent')) ?? []

/** Notes that a list was just saved to, so it is offered first next time. */
export async function markUsed(code: string): Promise<void> {
  const recent = (await getRecent()).filter((other) => other !== code)
  await write({ recent: [code, ...recent].slice(0, RECENT) })
}

const PENDING = 'pendingConnect'

export async function getPending(): Promise<PendingConnect | null> {
  const stored = await ext().storage.session.get(PENDING)
  return (stored[PENDING] as PendingConnect | undefined) ?? null
}

export const savePending = (pending: PendingConnect) =>
  ext().storage.session.set({ [PENDING]: pending })

export const clearPending = () => ext().storage.session.remove(PENDING)
