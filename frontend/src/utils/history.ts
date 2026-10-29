// Words for a list's history (docs/v2/11-UI-UX-MIGRATION.md#copy-synced-copy-and-history).
import type { LinkChange, Revision, RevisionSummary } from '../api'

/** Who made a version, as a phrase: "by Theo", "with the edit link", or "" if unknown. */
function byWhom(author: Revision['author']): string {
  if (author === 'edit link') return 'with the edit link'
  if (author === null) return ''
  return `by ${author.display_name.trim() || 'someone'}`
}

/** What a version is: "Edited by Theo", "Restored version 7 by Theo", "Created". */
export function describeRevision(revision: Revision): string {
  const who = byWhom(revision.author)
  const what = {
    created: 'Created',
    edited: 'Edited',
    restored: `Restored version ${revision.restored_from}`,
    forked: 'Copied from another list',
    migrated: 'History starts here (moved to the new version)',
  }[revision.kind]
  return revision.kind === 'migrated' || !who ? what : `${what} ${who}`
}

/** The change counts as short phrases: ["2 added", "1 removed", "renamed"]. */
export function summaryParts(summary: RevisionSummary): string[] {
  const parts: string[] = []
  if (summary.added) parts.push(`${summary.added} added`)
  if (summary.removed) parts.push(`${summary.removed} removed`)
  if (summary.modified) parts.push(`${summary.modified} edited`)
  if (summary.moved) parts.push(`${summary.moved} moved`)
  if (summary.list.includes('title')) parts.push('renamed')
  if (summary.list.includes('description')) parts.push('description changed')
  return parts
}

const FIELD_NAMES: Record<string, string> = {
  url: 'Link',
  title: 'Title',
  description: 'Description',
  icon: 'Icon',
  source_link_id: 'Copied from',
}

export const fieldName = (field: string) => FIELD_NAMES[field] ?? field

/** A link's name in a version: its title, or its URL without the scheme. */
export const linkName = (link: Pick<LinkChange, 'title' | 'url'>) =>
  link.title || link.url.replace(/^https?:\/\//, '')
