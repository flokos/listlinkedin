// Connecting this browser to an account (docs/v2/adr/ADR-020).
//
// 1. `startConnect` makes a PKCE pair, keeps it for this browser session and opens the site's
//    Connect page with the challenge.
// 2. The page asks, through the content script, whether this extension started the request
//    (`startedHere`), and shows nothing to approve otherwise.
// 3. The user approves there; the page hands over a one-time code, and `finishConnect`
//    exchanges it, with the verifier, for the session token.
import { ApiError, errorMessage, request } from './api'
import { siteUrl } from './config'
import { ext } from './ext'
import { browserName } from './pages'
import { newPkce } from './pkce'
import { clearPending, getPending, saveConnection, savePending } from './storage'

/** A request left open this long is forgotten: start again from the extension. */
const PENDING_FOR = 30 * 60_000

interface Connected {
  id: string
  name: string
  session_token: string
  user: { email: string }
}

/** Opens the site's Connect page in a new tab, for a new request. */
export async function startConnect(): Promise<void> {
  const { verifier, challenge } = await newPkce()
  await savePending({ verifier, challenge, startedAt: Date.now() })
  const query = new URLSearchParams({ challenge, name: browserName() })
  await ext().tabs.create({ url: siteUrl(`/connect-browser?${query}`) })
}

async function pendingFor(challenge: string) {
  const pending = await getPending()
  if (!pending || pending.challenge !== challenge) return null
  return Date.now() - pending.startedAt <= PENDING_FOR ? pending : null
}

/** Whether this extension asked to connect with `challenge` (and not too long ago). */
export const startedHere = async (challenge: string): Promise<boolean> =>
  (await pendingFor(challenge)) !== null

/**
 * Exchanges the code for the session token and keeps it. Throws an Error whose message the
 * Connect page shows.
 */
export async function finishConnect(challenge: string, code: string): Promise<void> {
  const pending = await pendingFor(challenge)
  if (!pending) throw new Error('This request has expired. Choose Connect in the extension again.')
  let connected: Connected
  try {
    connected = await request<Connected>('/api/v2/browsers/connect/', {
      method: 'POST',
      body: { code, verifier: pending.verifier },
    })
  } catch (error) {
    // A code can be tried again with the right verifier, so the request stays open after a
    // failure to reach the site; the server's refusal (invalid_code) ends it.
    if (error instanceof ApiError) await clearPending()
    throw new Error(errorMessage(error), { cause: error })
  }
  await saveConnection({
    id: connected.id,
    token: connected.session_token,
    name: connected.name,
    email: connected.user.email,
  })
  await clearPending()
}
