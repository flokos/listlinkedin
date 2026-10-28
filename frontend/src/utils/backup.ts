// Backup and restore of the lists saved in this browser. There are no accounts, so this
// file is how owners move their edit access to another device or keep a safety copy.
// It contains edit links: anyone holding it can change those lists.
import { buildEditLink } from '../composables/useEditLink'
import type { OwnedList } from '../composables/useOwnedLists'

export const BACKUP_APP = 'listlinkedin'
export const BACKUP_VERSION = 1

export interface BackupEntry {
  code: string
  token: string
  title?: string
}

export function createBackup(lists: OwnedList[], origin = window.location.origin) {
  return {
    app: BACKUP_APP,
    version: BACKUP_VERSION,
    exportedAt: new Date().toISOString(),
    note: 'PRIVATE: anyone with this file can edit or delete these lists.',
    lists: lists.map((l) => ({
      code: l.code,
      title: l.title,
      token: l.token,
      expiresAt: l.expiresAt,
      editLink: buildEditLink(l.code, l.token, origin),
    })),
  }
}

export function backupFilename(date = new Date()) {
  return `listlinkedin-saved-lists-${date.toISOString().slice(0, 10)}.json`
}

const EDIT_LINK = /\/l\/([A-Za-z0-9_-]+)\/manage\/?#t=([A-Za-z0-9_%-]+)/g

/**
 * Reads lists from a backup file. Accepts this app's JSON backups and, as a fallback, any
 * text containing edit links, such as the .txt file offered when a list is created.
 * Duplicates (same code) keep the last entry. Returns an empty array when nothing is found.
 */
export function parseBackup(text: string): BackupEntry[] {
  const found = new Map<string, BackupEntry>()
  try {
    const data: unknown = JSON.parse(text)
    if (data && typeof data === 'object' && Array.isArray((data as { lists?: unknown }).lists)) {
      for (const item of (data as { lists: unknown[] }).lists) {
        if (!item || typeof item !== 'object') continue
        const { code, token, title } = item as Record<string, unknown>
        if (typeof code === 'string' && typeof token === 'string' && code && token) {
          found.set(code, { code, token, title: typeof title === 'string' ? title : undefined })
        }
      }
      return [...found.values()]
    }
  } catch {
    // Not JSON: scan it for edit links below.
  }
  for (const match of text.matchAll(EDIT_LINK)) {
    const code = match[1]!
    found.set(code, { code, token: decodeURIComponent(match[2]!) })
  }
  return [...found.values()]
}
