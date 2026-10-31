import { describe, expect, it } from 'vitest'

import type { Revision } from '../api'
import { describeRevision, summaryParts } from './history'

const base: Revision = {
  number: 2,
  kind: 'edited',
  created_at: '2026-10-29T10:00:00Z',
  author: { display_name: 'Theo' },
  summary: { added: 0, removed: 0, modified: 0, moved: 0, list: [] },
  restored_from: null,
}

describe('history wording', () => {
  it('names who made each kind of version', () => {
    expect(describeRevision(base)).toBe('Edited by Theo')
    expect(describeRevision({ ...base, author: 'edit link' })).toBe('Edited with the edit link')
    expect(describeRevision({ ...base, author: { display_name: ' ' } })).toBe('Edited by someone')
    expect(describeRevision({ ...base, kind: 'restored', restored_from: 7 })).toBe(
      'Restored version 7 by Theo',
    )
    expect(describeRevision({ ...base, kind: 'migrated', author: null })).toBe(
      'History starts here (moved to the new version)',
    )
    expect(describeRevision({ ...base, kind: 'created', author: null })).toBe('Created')
  })

  it('summarizes the counts', () => {
    const summary = { added: 2, removed: 1, modified: 0, moved: 3, list: ['title'] }
    expect(summaryParts(summary)).toEqual(['2 added', '1 removed', '3 moved', 'renamed'])
    expect(summaryParts(base.summary)).toEqual([])
  })
})
