// Connected browsers (docs/v2/adr/ADR-020): the browser extension is approved on this site,
// then signs in by itself. Shapes follow backend/apps/accounts/serializers.py.
import { request } from './client'

export interface ConnectedBrowser {
  id: string
  /** What the extension called itself, e.g. "Firefox on Linux". */
  name: string
  connected_at: string
  /** Updated at most once a day. */
  last_used_at: string
  /** The connection the request itself came from: never true on this site. */
  current: boolean
}

/**
 * Lets a browser connect. Answers with a one-time code for the extension, which is worth
 * nothing without the verifier behind `challenge`. 409 `too_many_browsers` at ten.
 */
export const approveBrowser = (challenge: string, name: string) =>
  request<{ code: string; expires_in: number }>('/api/v2/me/browsers/approvals/', {
    method: 'POST',
    body: { challenge, name },
  })

/** The browsers connected to the account that still work, newest first. */
export const listBrowsers = (signal?: AbortSignal) =>
  request<ConnectedBrowser[]>('/api/v2/me/browsers/', { signal })

/** Ends a connection: the extension there is signed out at once. */
export const disconnectBrowser = (id: string) =>
  request<null>(`/api/v2/me/browsers/${encodeURIComponent(id)}/`, { method: 'DELETE' })
