// What the right-click menus and the keyboard shortcuts do. They save and copy without
// opening anything; only "Choose a list…" shows a window. How it went is said by a mark on the
// toolbar button (src/lib/feedback.ts).
import { Disconnected } from '../lib/account'
import { errorMessage } from '../lib/api'
import { copyText } from '../lib/clipboard'
import { siteUrl } from '../lib/config'
import { ext } from '../lib/ext'
import { done, problem } from '../lib/feedback'
import { lastUsedList, savePage } from '../lib/lists'
import { type PageToSave, titleFrom, whyNotSaveable } from '../lib/pages'
import { getCachedLists, getConnection } from '../lib/storage'
import { whoCanOpen } from '../lib/visibility'

const NOT_CONNECTED = "This browser isn't connected to listlinkedin yet."
const NO_LAST_LIST =
  'Save a page from here once. After that, the shortcuts use the list you saved to last.'

/** A page's address, short enough to say: `example.com/some/long/pa…`. */
export function shortAddress(url: string): string {
  try {
    const { host, pathname } = new URL(url)
    const text = host.replace(/^www\./, '') + (pathname === '/' ? '' : pathname)
    return text.length > 40 ? `${text.slice(0, 39)}…` : text
  } catch {
    return 'This page'
  }
}

/** A tab as a page to save. */
export const pageOfTab = (tab: { url?: string; title?: string } | undefined): PageToSave => ({
  url: tab?.url ?? '',
  title: titleFrom(tab?.title),
})

/** The tab in front, as a shortcut means it. */
export async function frontPage(): Promise<PageToSave> {
  const [tab] = await ext().tabs.query({ active: true, lastFocusedWindow: true })
  return pageOfTab(tab)
}

/** Saves `page` into the list with this code. */
export async function saveTo(code: string, page: PageToSave): Promise<void> {
  const blocked = whyNotSaveable(page.url)
  if (blocked) return problem(blocked, 'info')
  const list = ((await getCachedLists()) ?? []).find((other) => other.code === code)
  const name = list ? `“${list.title}”` : 'that list'
  try {
    // One key per click: a second click is a second wish, and the site says "already there".
    const outcome = await savePage(code, page, crypto.randomUUID())
    if (outcome.saved) await done()
    else
      await problem(`${shortAddress(page.url)} wasn't saved to ${name}. ${outcome.reason}`, 'info')
  } catch (error) {
    if (error instanceof Disconnected) await problem(NOT_CONNECTED, 'info')
    else await problem(`${shortAddress(page.url)} wasn't saved to ${name}. ${errorMessage(error)}`)
  }
}

/** Saves `page` into the list saved to last. It never picks another list by itself. */
export async function saveToLastList(page: PageToSave): Promise<void> {
  if (!(await getConnection())) return problem(NOT_CONNECTED, 'info')
  const list = await lastUsedList()
  if (!list?.canEdit) return problem(NO_LAST_LIST, 'info')
  return saveTo(list.code, page)
}

/** Copies the link of the list saved to last. Copying changes nothing about who can open it. */
export async function copyLastListLink(): Promise<void> {
  if (!(await getConnection())) return problem(NOT_CONNECTED, 'info')
  const list = await lastUsedList()
  if (!list) return problem(NO_LAST_LIST, 'info')
  try {
    await copyText(list.url)
  } catch {
    return problem(`The browser didn't let the extension copy the link to “${list.title}”.`)
  }
  // A private list's link opens for nobody new: worth knowing before it is pasted somewhere.
  await done(
    list.visibility === 'private'
      ? `You copied the link to “${list.title}”. ${whoCanOpen('private', 'list', list.canSet)}`
      : undefined,
  )
}

/** The popup's size as a window of its own. */
const CHOOSER = { width: 392, height: 640 }

/**
 * Opens the popup in a small window of its own, about `page`: choosing a list for a link that
 * was right-clicked (the toolbar popup is always about the tab in front).
 */
export async function openChooser(page: PageToSave): Promise<void> {
  const query = new URLSearchParams({ url: page.url, title: page.title })
  await ext().windows.create({
    url: ext().runtime.getURL(`popup.html?${query}`),
    type: 'popup',
    ...CHOOSER,
  })
}

export async function openMyLists(): Promise<void> {
  await ext().tabs.create({ url: siteUrl('/lists') })
}

/** The keyboard shortcuts' names, as the manifest declares them (scripts/manifest.ts). */
export const SAVE_PAGE = 'save-page'
export const COPY_LIST_LINK = 'copy-list-link'

/** Does what a keyboard shortcut asks. Browsers that pass the tab in front spare a lookup. */
export async function runCommand(
  command: string,
  tab?: { url?: string; title?: string },
): Promise<void> {
  if (command === SAVE_PAGE) return saveToLastList(tab?.url ? pageOfTab(tab) : await frontPage())
  if (command === COPY_LIST_LINK) return copyLastListLink()
}
