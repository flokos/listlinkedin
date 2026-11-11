// Chrome only: the document its service worker opens to copy text, since a service worker has
// no clipboard (src/lib/clipboard.ts). It is never shown, copies what the background script
// sends it, and is closed again. Firefox's background page copies by itself.
import { copyBySelection, copyRequest } from '../lib/clipboard'
import { ext } from '../lib/ext'

ext().runtime.onMessage.addListener((message, sender, sendResponse) => {
  // Only the extension's own background script: a tab's content script is not it.
  const request = sender.id === ext().runtime.id && !sender.tab ? copyRequest(message) : null
  if (!request) return false
  sendResponse({ ok: copyBySelection(request.text) })
  return false
})
