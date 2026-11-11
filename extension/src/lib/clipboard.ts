// Copying text, from wherever the extension runs.
//
// - A page of the extension (the popup) and Firefox's background page have a document: the
//   clipboard is right there.
// - Chrome's background script is a service worker, which has neither a document nor a
//   clipboard. It opens an offscreen document (offscreen.html), which copies for it and is
//   closed again.
//
// Outside a click, both browsers want the `clipboardWrite` permission for this.
import { ext } from './ext'

export const OFFSCREEN_COPY = 'offscreen:copy'

/** What the background script asks of the offscreen document. */
export interface CopyRequest {
  type: typeof OFFSCREEN_COPY
  text: string
}

export function copyRequest(message: unknown): CopyRequest | null {
  if (!message || typeof message !== 'object') return null
  const { type, text } = message as Record<string, unknown>
  return type === OFFSCREEN_COPY && typeof text === 'string' ? { type, text } : null
}

/** Copies with a selection: what works in a document that can't have the focus. */
export function copyBySelection(text: string, doc: Document = document): boolean {
  const area = doc.createElement('textarea')
  area.value = text
  doc.body.append(area)
  area.select()
  try {
    return doc.execCommand('copy')
  } catch {
    return false
  } finally {
    area.remove()
  }
}

async function throughOffscreen(text: string): Promise<void> {
  const { offscreen, runtime } = ext()
  if (!(await offscreen.hasDocument()))
    await offscreen.createDocument({
      url: 'offscreen.html',
      reasons: ['CLIPBOARD' as chrome.offscreen.Reason],
      justification: 'Copies the link of a list when you ask for it with a shortcut or a menu.',
    })
  try {
    const reply = (await runtime.sendMessage({
      type: OFFSCREEN_COPY,
      text,
    } satisfies CopyRequest)) as { ok?: boolean } | undefined
    if (!reply?.ok) throw new Error('The browser refused to copy.')
  } finally {
    await offscreen.closeDocument().catch(() => {})
  }
}

/** Puts `text` on the clipboard. Rejects when the browser won't allow it. */
export async function copyText(text: string): Promise<void> {
  if (typeof document === 'undefined') return throughOffscreen(text)
  try {
    await navigator.clipboard.writeText(text)
  } catch (error) {
    // A page without the focus (a popup window behind another one) may still select and copy.
    if (!copyBySelection(text)) throw error
  }
}
