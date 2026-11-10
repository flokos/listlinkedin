// The messages between the site's Connect page and this extension (docs/v2/adr/ADR-020).
// The page's half is frontend/src/utils/extensionBridge.ts: change them together.
//
// The content script (src/content/bridge.ts) runs on the site only. It and the page post
// plain objects on the page's window, to the site's origin, and accept only messages from
// that window and origin:
//
//   page → extension   hello  {challenge}           is the extension here, and did it ask?
//   extension → page   ready  {challenge, started}  started: it opened this page itself
//   page → extension   code   {challenge, code}     after the user approved
//   extension → page   connected | failed {challenge, message?}
//
// The content script passes them on to the background script, which holds the verifier:

export const PAGE = 'listlinkedin-page'
export const EXTENSION = 'listlinkedin-extension'

export type PageMessage =
  | { source: typeof PAGE; type: 'hello'; challenge: string }
  | { source: typeof PAGE; type: 'code'; challenge: string; code: string }

export type ExtensionMessage =
  | { source: typeof EXTENSION; type: 'ready'; challenge: string; started: boolean }
  | { source: typeof EXTENSION; type: 'connected'; challenge: string }
  | { source: typeof EXTENSION; type: 'failed'; challenge: string; message?: string }

/** What the content script asks the background script. */
export type ConnectRequest =
  | { type: 'connect:started'; challenge: string }
  | { type: 'connect:code'; challenge: string; code: string }

export type ConnectReply = { started: boolean } | { ok: true } | { ok: false; message: string }

const CHALLENGE = /^[A-Za-z0-9_-]{43}$/

/** The page's message in `data`, or null for anything that isn't one. */
export function pageMessage(data: unknown): PageMessage | null {
  if (!data || typeof data !== 'object') return null
  const message = data as Record<string, unknown>
  if (message.source !== PAGE || typeof message.challenge !== 'string') return null
  if (!CHALLENGE.test(message.challenge)) return null
  const challenge = message.challenge
  if (message.type === 'hello') return { source: PAGE, type: 'hello', challenge }
  if (message.type === 'code' && typeof message.code === 'string' && message.code.length <= 128)
    return { source: PAGE, type: 'code', challenge, code: message.code }
  return null
}

/** The same check for what reaches the background script. */
export function connectRequest(data: unknown): ConnectRequest | null {
  if (!data || typeof data !== 'object') return null
  const message = data as Record<string, unknown>
  if (typeof message.challenge !== 'string' || !CHALLENGE.test(message.challenge)) return null
  const challenge = message.challenge
  if (message.type === 'connect:started') return { type: 'connect:started', challenge }
  if (
    message.type === 'connect:code' &&
    typeof message.code === 'string' &&
    message.code.length <= 128
  )
    return { type: 'connect:code', challenge, code: message.code }
  return null
}
