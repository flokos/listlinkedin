// Saving several pages into a list at once (POST /api/v2/lists/{code}/links/batch/). The
// site takes at most 100 links and 16 KB per request, so the pages are sent in parts; each
// part is one change in the list's history.
import { asAccount } from './account'
import type { PageToSave } from './pages'
import { markUsed } from './storage'

/** The site's limits (backend: MAX_LINKS_PER_LIST, DATA_UPLOAD_MAX_MEMORY_SIZE), with room to spare. */
export const PART_LINKS = 100
export const PART_BYTES = 12 * 1024

type Reason = 'duplicate' | 'invalid' | 'list_full'

interface BatchAnswer {
  added: unknown[]
  skipped: { index: number; reason: Reason }[]
}

export interface BatchResult {
  saved: number
  /** Already in the list. */
  duplicate: number
  /** Addresses the site refused. */
  invalid: number
  /** Didn't fit: a list holds 100 links. */
  full: number
  /** Not sent, because an earlier part failed. */
  unsent: number
}

const item = (page: PageToSave) => ({ destination_url: page.url, title: page.title || null })
const bytes = (value: unknown) => new TextEncoder().encode(JSON.stringify(value)).length

/** `pages` in parts the site accepts, in order. */
export function parts(pages: PageToSave[]): PageToSave[][] {
  const out: PageToSave[][] = []
  let part: PageToSave[] = []
  let size = 0
  for (const page of pages) {
    const next = bytes(item(page)) + 1
    if (part.length && (part.length >= PART_LINKS || size + next > PART_BYTES)) {
      out.push(part)
      part = []
      size = 0
    }
    part.push(page)
    size += next
  }
  if (part.length) out.push(part)
  return out
}

/** What `saveMany` throws when a part fails: what the earlier parts did, and why it stopped. */
export class BatchStopped extends Error {
  constructor(
    readonly result: BatchResult,
    readonly reason: unknown,
  ) {
    super('Not every page was sent.')
    this.name = 'BatchStopped'
  }
}

/**
 * Saves `pages` into the list, in order. The site skips what is already there, what it
 * refuses and what no longer fits, and says so; this adds it up. Titles are the tabs' or the
 * history's, so what the site fetches later never replaces them (invariant 6).
 */
export async function saveMany(list: string, pages: PageToSave[]): Promise<BatchResult> {
  const result: BatchResult = { saved: 0, duplicate: 0, invalid: 0, full: 0, unsent: pages.length }
  for (const part of parts(pages)) {
    let answer: BatchAnswer
    try {
      answer = await asAccount<BatchAnswer>(
        `/api/v2/lists/${encodeURIComponent(list)}/links/batch/`,
        { method: 'POST', body: { links: part.map(item) } },
      )
    } catch (error) {
      if (result.saved) await markUsed(list)
      throw new BatchStopped(result, error)
    }
    result.unsent -= part.length
    result.saved += answer.added.length
    for (const { reason } of answer.skipped) result[reason === 'list_full' ? 'full' : reason] += 1
  }
  if (result.saved) await markUsed(list)
  return result
}

const count = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

/** The result in a sentence: "37 pages saved, 3 were already there, 5 didn't fit." */
export function describe(result: BatchResult): string {
  const said = [count(result.saved, 'page saved', 'pages saved')]
  if (result.duplicate)
    said.push(count(result.duplicate, 'was already there', 'were already there'))
  if (result.full)
    said.push(`${count(result.full, "didn't fit", "didn't fit")} (a list holds 100 links)`)
  if (result.invalid)
    said.push(count(result.invalid, "address wasn't accepted", "addresses weren't accepted"))
  if (result.unsent) said.push(count(result.unsent, "wasn't sent", "weren't sent"))
  return `${said.join(', ')}.`
}
