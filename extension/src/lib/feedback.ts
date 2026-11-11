// Saying how it went when there is no window to say it in (a right-click menu, a keyboard
// shortcut): a mark on the toolbar button, and for anything but plain success a sentence the
// popup shows the next time it opens.
import { ext } from './ext'
import { saveOutcome } from './storage'

/** How long the mark for a success stays. A problem's stays until the popup is opened. */
export const DONE_FOR = 4000

const DONE = { text: '✓', color: '#1b7a43' }
const PROBLEM = { text: '!', color: '#b3263e' }

async function badge(mark: { text: string; color: string } | null): Promise<void> {
  const { action } = ext()
  await action.setBadgeText({ text: mark?.text ?? '' })
  if (mark) await action.setBadgeBackgroundColor({ color: mark.color })
}

/** It worked: a check mark for a moment. `note`, if given, is still worth reading later. */
export async function done(note?: string): Promise<void> {
  if (note) await saveOutcome({ tone: 'info', text: note, at: Date.now() })
  await badge(DONE)
  setTimeout(() => void badge(null).catch(() => {}), DONE_FOR)
}

/** It didn't: an exclamation mark, and why, until the popup is opened. */
export async function problem(text: string, tone: 'info' | 'error' = 'error'): Promise<void> {
  await saveOutcome({ tone, text, at: Date.now() })
  await badge(PROBLEM)
}

/** The popup is open: whatever the mark was about, it is being read now. */
export const clearMark = (): Promise<void> => badge(null)
