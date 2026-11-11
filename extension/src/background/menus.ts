// The right-click menus.
//
// On a page or a link: "Save to listlinkedin" with the lists saved to last, and "Choose a
// list…", then "Save open tabs…" and "Save from history…", which open the page for saving
// several at once. On the toolbar button: "Copy link to …" for the list saved to last, the
// same two, and "Open my lists". The menus are made again whenever what they show changes (the connection, the
// lists, the ones used last), so they are right even while the background script is asleep.
import { ext } from '../lib/ext'
import { byLastUse } from '../lib/lists'
import type { PageToSave } from '../lib/pages'
import { getCachedLists, getConnection, getRecent, type ListSummary } from '../lib/storage'
import {
  copyLastListLink,
  openChooser,
  openMyLists,
  openPicker,
  pageOfTab,
  saveTo,
} from './actions'

/** How many lists the menu offers; the rest are behind "Choose a list…". */
export const MENU_LISTS = 6

const SAVE = 'save'
const SAVE_TO = 'save-to:'
const CHOOSE = 'choose'
const COPY_LINK = 'copy-link'
const MY_LISTS = 'my-lists'
// Several pages at once: once under "Save to listlinkedin", once on the toolbar button.
const SEVERAL = { tabs: 'Save open tabs…', history: 'Save from history…' } as const
const SEVERAL_FROM = 'several:'
const ON_BUTTON = ':button'

type Context = 'page' | 'link' | 'action'

export interface MenuItem {
  id: string
  title?: string
  type?: 'separator'
  parentId?: string
  contexts: [Context, ...Context[]]
}

/** A title as a menu entry: short, and with nothing a menu would read as a command. */
export function menuTitle(title: string): string {
  const short = title.length > 40 ? `${title.slice(0, 39)}…` : title
  // In a menu "&" marks an access key, and Chrome puts the selected text where "%s" is.
  return short.replace(/&/g, '&&').replace(/%s/g, '%​s')
}

/** The menus for this state, in order. */
export function menuItems(state: {
  connected: boolean
  lists: ListSummary[]
  recent: string[]
}): MenuItem[] {
  const onPage: MenuItem['contexts'] = ['page', 'link']
  // Not connected: one entry, which opens the window that offers to connect.
  if (!state.connected) return [{ id: CHOOSE, title: 'Save to listlinkedin…', contexts: onPage }]

  const offered = byLastUse(
    state.lists.filter((list) => list.canEdit),
    state.recent,
  ).slice(0, MENU_LISTS)
  const items: MenuItem[] = [
    { id: SAVE, title: 'Save to listlinkedin', contexts: onPage },
    ...offered.map((list): MenuItem => ({
      id: SAVE_TO + list.code,
      parentId: SAVE,
      title: menuTitle(list.title),
      contexts: onPage,
    })),
  ]
  if (offered.length)
    items.push({ id: 'separator', parentId: SAVE, type: 'separator', contexts: onPage })
  items.push({ id: CHOOSE, parentId: SAVE, title: 'Choose a list…', contexts: onPage })
  items.push({ id: 'separator-several', parentId: SAVE, type: 'separator', contexts: onPage })
  for (const [source, title] of Object.entries(SEVERAL))
    items.push({ id: SEVERAL_FROM + source, parentId: SAVE, title, contexts: onPage })

  const last = state.lists.find((list) => list.code === state.recent[0])
  if (last)
    items.push({
      id: COPY_LINK,
      title: `Copy link to “${menuTitle(last.title)}”`,
      contexts: ['action'],
    })
  // Chrome shows at most six entries of an extension on its toolbar button: these are four.
  for (const [source, title] of Object.entries(SEVERAL))
    items.push({ id: SEVERAL_FROM + source + ON_BUTTON, title, contexts: ['action'] })
  items.push({ id: MY_LISTS, title: 'Open my lists', contexts: ['action'] })
  return items
}

let built: string | undefined
let queue: Promise<void> = Promise.resolve()

async function build(force: boolean): Promise<void> {
  const [connection, lists, recent] = await Promise.all([
    getConnection(),
    getCachedLists(),
    getRecent(),
  ])
  const items = menuItems({ connected: connection !== null, lists: lists ?? [], recent })
  const wanted = JSON.stringify(items)
  if (!force && wanted === built) return
  const menus = ext().contextMenus
  await menus.removeAll()
  // A failure to make one entry (reported through lastError) must not lose the others. It is
  // worth a line in the extension's console: an entry that is missing is hard to notice.
  for (const item of items)
    menus.create(item as chrome.contextMenus.CreateProperties, () => {
      const failure = ext().runtime.lastError
      // The entry's kind only: a list's code is its address, and stays out of logs.
      if (failure)
        console.warn(`listlinkedin: no menu entry "${item.id.split(':')[0]}": ${failure.message}`)
    })
  built = wanted
}

/**
 * Makes the menus as they should be now. Calls are run one after the other: two at once
 * would each remove and add, and collide. `force` builds even if nothing seems to have
 * changed: after an install or a browser start, when the browser may have none.
 */
export function rebuildMenus(force = false): Promise<void> {
  queue = queue.then(() => build(force)).catch(() => {})
  return queue
}

/** What a click on a page or a link is about. */
export function pageOfClick(
  info: { linkUrl?: string; pageUrl?: string },
  tab: { url?: string; title?: string } | undefined,
): PageToSave {
  // A link: its address only. A link's text is rarely a title ("here", "read more"), so the
  // list shows the page's own once the site has fetched it.
  if (info.linkUrl) return { url: info.linkUrl, title: '' }
  return { ...pageOfTab(tab), url: info.pageUrl ?? tab?.url ?? '' }
}

export async function onMenuClick(
  info: { menuItemId: string | number; linkUrl?: string; pageUrl?: string },
  tab?: { url?: string; title?: string },
): Promise<void> {
  const id = String(info.menuItemId)
  if (id === COPY_LINK) return copyLastListLink()
  if (id === MY_LISTS) return openMyLists()
  if (id.startsWith(SEVERAL_FROM)) {
    const source = id.slice(SEVERAL_FROM.length).replace(ON_BUTTON, '')
    if (source === 'tabs' || source === 'history') return openPicker(source)
    return
  }
  if (id === CHOOSE) return openChooser(pageOfClick(info, tab))
  if (id.startsWith(SAVE_TO)) return saveTo(id.slice(SAVE_TO.length), pageOfClick(info, tab))
}
