// The connected account: calling the API as it, and disconnecting.
import { ApiError, request, type RequestOptions } from './api'
import { forgetAccount, getConnection } from './storage'

/** This browser isn't connected, or the site ended the connection. */
export class Disconnected extends Error {
  constructor() {
    super('This browser is not connected to listlinkedin.')
    this.name = 'Disconnected'
  }
}

/**
 * Calls the API as the connected account. A 401 means the connection is over (disconnected on
 * the site, unused for too long, a new password): the extension forgets the account, and the
 * popup offers to connect again.
 */
export async function asAccount<T>(
  path: string,
  options: Omit<RequestOptions, 'token'> = {},
): Promise<T> {
  const connection = await getConnection()
  if (!connection) throw new Disconnected()
  try {
    return await request<T>(path, { ...options, token: connection.token })
  } catch (error) {
    if (!(error instanceof ApiError && error.status === 401)) throw error
    // Unless a new connection was made meanwhile: that one stays.
    if ((await getConnection())?.token === connection.token) await forgetAccount()
    throw new Disconnected()
  }
}

/**
 * Disconnects this browser: ends the session on the site, then forgets the account here. The
 * account is forgotten even if the site can't be reached (it ends the session by itself after
 * 90 days without use; the account page can end it sooner).
 */
export async function disconnect(): Promise<void> {
  const connection = await getConnection()
  if (!connection) return
  try {
    await request<null>(`/api/v2/me/browsers/${encodeURIComponent(connection.id)}/`, {
      method: 'DELETE',
      token: connection.token,
    })
  } catch {
    // Gone already, or unreachable: either way this browser lets go of the token.
  }
  await forgetAccount()
}
