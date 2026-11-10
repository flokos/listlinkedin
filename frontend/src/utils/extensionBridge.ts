// How the Connect page talks to the browser extension (docs/v2/adr/ADR-020). The extension's
// content script runs on this site only. Both sides post plain objects on this window, to this
// origin, and accept only messages from this window and origin: another site can neither send
// nor read them. The one-time code travels this way, never in a URL.
//
//   page → extension   hello  {challenge}           is the extension here, and did it ask?
//   extension → page   ready  {challenge, started}  started: it opened this page itself
//   page → extension   code   {challenge, code}     after the user approved
//   extension → page   connected | failed {challenge, message?}
//
// `challenge` (PKCE, S256) names the request; the extension keeps the verifier to itself, so
// the code is useless to anything else that hears it.

export const PAGE = 'listlinkedin-page'
export const EXTENSION = 'listlinkedin-extension'

export type PageMessage =
  | { source: typeof PAGE; type: 'hello'; challenge: string }
  | { source: typeof PAGE; type: 'code'; challenge: string; code: string }

export type ExtensionMessage =
  | { source: typeof EXTENSION; type: 'ready'; challenge: string; started: boolean }
  | { source: typeof EXTENSION; type: 'connected'; challenge: string }
  | { source: typeof EXTENSION; type: 'failed'; challenge: string; message?: string }

const post = (message: PageMessage) => window.postMessage(message, window.location.origin)

/** The extension's message in `event` about `challenge`, or null for anything else. */
export function extensionMessage(event: MessageEvent, challenge: string): ExtensionMessage | null {
  if (event.source !== window || event.origin !== window.location.origin) return null
  const data = event.data as Partial<ExtensionMessage> | null
  if (!data || typeof data !== 'object' || data.source !== EXTENSION) return null
  if (data.challenge !== challenge) return null
  if (data.type === 'ready')
    return { source: EXTENSION, type: 'ready', challenge, started: data.started === true }
  if (data.type === 'connected') return { source: EXTENSION, type: 'connected', challenge }
  if (data.type === 'failed') {
    const message = typeof data.message === 'string' ? data.message.slice(0, 200) : undefined
    return { source: EXTENSION, type: 'failed', challenge, message }
  }
  return null
}

/** Waits for the extension's next message about `challenge` that `pick` accepts. */
function waitFor<T>(
  challenge: string,
  pick: (message: ExtensionMessage) => T | undefined,
  timeout: number,
  onTick?: () => void,
  interval = 250,
): Promise<T | null> {
  return new Promise((resolve) => {
    const finish = (value: T | null) => {
      window.removeEventListener('message', listener)
      window.clearTimeout(deadline)
      window.clearInterval(ticker)
      resolve(value)
    }
    const listener = (event: MessageEvent) => {
      const message = extensionMessage(event, challenge)
      const value = message ? pick(message) : undefined
      if (value !== undefined) finish(value)
    }
    window.addEventListener('message', listener)
    const deadline = window.setTimeout(() => finish(null), timeout)
    const ticker = onTick ? window.setInterval(onTick, interval) : undefined
    onTick?.()
  })
}

/**
 * Asks whether the extension is in this browser. Resolves true if it opened this page for
 * `challenge` itself, false if it is here but didn't (someone else's link), and null if no
 * extension answered. The content script may load a moment after the page, so it asks again
 * until `timeout`.
 */
export function findExtension(challenge: string, timeout = 2500): Promise<boolean | null> {
  return waitFor(
    challenge,
    (message) => (message.type === 'ready' ? message.started : undefined),
    timeout,
    () => post({ source: PAGE, type: 'hello', challenge }),
  )
}

/**
 * Hands the one-time code to the extension and waits until it has connected. Rejects with
 * the extension's reason, or when it doesn't answer in time.
 */
export async function sendCode(challenge: string, code: string, timeout = 20_000): Promise<void> {
  const answer = waitFor(
    challenge,
    (message) => (message.type === 'connected' || message.type === 'failed' ? message : undefined),
    timeout,
  )
  post({ source: PAGE, type: 'code', challenge, code })
  const message = await answer
  if (message?.type === 'connected') return
  throw new Error(
    (message?.type === 'failed' && message.message) ||
      "The extension didn't answer. Go back to it and choose Connect again.",
  )
}
