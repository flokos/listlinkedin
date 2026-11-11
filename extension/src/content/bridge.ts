// The content script. It runs on the listlinkedin site only (the manifest's one match), and
// does one thing: it carries the Connect page's messages to the background script and the
// answers back (src/lib/bridge.ts, docs/v2/adr/ADR-020).
//
// It holds no secret. The verifier and the session token stay in the background script; the
// one-time code passes through, and is useless without the verifier.
import {
  type ConnectReply,
  type ConnectRequest,
  EXTENSION,
  type ExtensionMessage,
  pageMessage,
} from '../lib/bridge'
import { ext } from '../lib/ext'

const post = (message: ExtensionMessage) => window.postMessage(message, window.location.origin)

const ask = (request: ConnectRequest) =>
  ext().runtime.sendMessage(request) as Promise<ConnectReply | undefined>

window.addEventListener('message', (event: MessageEvent) => {
  // Only what this page posted to itself: never another window or another site.
  if (event.source !== window || event.origin !== window.location.origin) return
  const message = pageMessage(event.data)
  if (!message) return
  const { challenge } = message

  if (message.type === 'hello') {
    const ready = (started: boolean) =>
      post({ source: EXTENSION, type: 'ready', challenge, started })
    ask({ type: 'connect:started', challenge }).then(
      (reply) => ready(reply !== undefined && 'started' in reply && reply.started),
      () => ready(false),
    )
    return
  }

  const failed = (text?: string) =>
    post({ source: EXTENSION, type: 'failed', challenge, message: text })
  ask({ type: 'connect:code', challenge, code: message.code }).then(
    (reply) => {
      if (reply !== undefined && 'ok' in reply && reply.ok)
        post({ source: EXTENSION, type: 'connected', challenge })
      else failed(reply !== undefined && 'ok' in reply ? reply.message : undefined)
    },
    () => failed(),
  )
})
