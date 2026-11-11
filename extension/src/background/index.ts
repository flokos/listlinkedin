// The background script: a service worker in Chrome, an event page in Firefox. It starts on
// an event and may stop when idle, so it keeps nothing in memory: state lives in storage.
//
// - On install, it opens the welcome page.
// - It answers the content script on the site's Connect page: whether this extension asked to
//   connect, and the exchange of the one-time code (src/lib/connect.ts). The PKCE verifier
//   and the session token never leave the background script and the extension's own pages.
import { connectRequest, type ConnectReply } from '../lib/bridge'
import { onSite } from '../lib/config'
import { finishConnect, startedHere } from '../lib/connect'
import { ext } from '../lib/ext'

ext().runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install')
    void ext().tabs.create({ url: ext().runtime.getURL('welcome.html') })
})

/** Only this extension's content script, in the top frame of a page of the site. */
function fromSitePage(sender: chrome.runtime.MessageSender): boolean {
  return (
    sender.id === ext().runtime.id &&
    sender.tab !== undefined &&
    sender.frameId === 0 &&
    onSite(sender.url)
  )
}

async function answer(message: unknown): Promise<ConnectReply | undefined> {
  const request = connectRequest(message)
  if (!request) return undefined
  if (request.type === 'connect:started') return { started: await startedHere(request.challenge) }
  try {
    await finishConnect(request.challenge, request.code)
    return { ok: true }
  } catch (error) {
    return { ok: false, message: (error as Error).message }
  }
}

// `return true` keeps the channel open for an answer that comes later: the one form both
// browsers accept from a listener.
ext().runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!fromSitePage(sender)) return false
  answer(message).then(sendResponse, () => sendResponse(undefined))
  return true
})
