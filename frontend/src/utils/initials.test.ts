import { describe, expect, it } from 'vitest'

import { initialsOf } from './initials'

describe('initialsOf', () => {
  it.each([
    ['Backend tools', 'BT'],
    ['  dev   portal docs ', 'DP'],
    ['Database', 'DA'],
    ['é', 'É'],
    ['😀 smile', '😀S'],
    ['', '?'],
  ])('%j → %s', (title, initials) => expect(initialsOf(title)).toBe(initials))
})
