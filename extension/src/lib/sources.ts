// Where the picker's pages come from: the open tabs and the browsing history. Both are read
// inside the browser and need a permission the user gave for it (src/lib/permissions.ts).
import { ext } from './ext'
import { type PageToSave, titleFrom, whyNotSaveable } from './pages'

/** The most history entries offered at once: enough to pick from, and quick to draw. */
export const HISTORY_SHOWN = 200

/** The pages the site would take, each address once, in the order given. */
export function saveable(pages: { url?: string; title?: string }[]): PageToSave[] {
  const seen = new Set<string>()
  const kept: PageToSave[] = []
  for (const page of pages) {
    if (!page.url || seen.has(page.url) || whyNotSaveable(page.url)) continue
    seen.add(page.url)
    kept.push({ url: page.url, title: titleFrom(page.title) })
  }
  return kept
}

/** The open tabs of every ordinary window, in the browser's order. Private windows are left out. */
export async function openTabs(): Promise<PageToSave[]> {
  const tabs = await ext().tabs.query({})
  return saveable(tabs.filter((tab) => !tab.incognito))
}

/** Pages from the history, the latest visit first, matching `text` if given. */
export async function historyPages(text = ''): Promise<PageToSave[]> {
  const found = await ext().history.search({
    text: text.trim(),
    startTime: 0,
    maxResults: HISTORY_SHOWN,
  })
  const latestFirst = [...found].sort((a, b) => (b.lastVisitTime ?? 0) - (a.lastVisitTime ?? 0))
  return saveable(latestFirst)
}
