import { describe, expect, it } from 'vitest'

import { backupFilename, createBackup, parseBackup } from './backup'

const token = 'q9Xx-3k_AbCdEfGhIjKlMnOpQrStUvWxYz0123456789'
const saved = [
  {
    code: 'CODE1',
    token,
    title: 'Team',
    expiresAt: '2026-12-01T00:00:00Z',
    savedAt: '2026-10-01T00:00:00Z',
  },
]

describe('backups', () => {
  it('round-trips through JSON', () => {
    const backup = createBackup(saved, 'https://go.example.com')
    expect(backup.lists[0]!.editLink).toBe(`https://go.example.com/l/CODE1/manage#t=${token}`)
    expect(parseBackup(JSON.stringify(backup))).toEqual([{ code: 'CODE1', token, title: 'Team' }])
  })

  it('reads edit links from the .txt saved at creation', () => {
    const text = [
      'listlinkedin: Team',
      'Share link (anyone can view):',
      'https://go.example.com/l/CODE1',
      'Edit link (PRIVATE, anyone with it can change or delete the list):',
      `https://go.example.com/l/CODE1/manage#t=${token}`,
    ].join('\n')
    expect(parseBackup(text)).toEqual([{ code: 'CODE1', token }])
  })

  it('skips malformed entries and keeps one entry per list', () => {
    const json = JSON.stringify({
      lists: [{ code: 'A', token: 't1' }, { code: 'A', token: 't2' }, { code: 'B' }, null, 'x'],
    })
    expect(parseBackup(json)).toEqual([{ code: 'A', token: 't2', title: undefined }])
  })

  it('finds nothing in unrelated files', () => {
    expect(parseBackup('hello')).toEqual([])
    expect(parseBackup('{"a": 1}')).toEqual([])
  })

  it('names files by date', () => {
    expect(backupFilename(new Date('2026-10-28T09:00:00Z'))).toBe(
      'listlinkedin-saved-lists-2026-10-28.json',
    )
  })
})
