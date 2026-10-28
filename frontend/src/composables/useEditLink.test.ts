import { describe, expect, it } from 'vitest'

import { buildEditLink, parseEditInput, tokenFromHash } from './useEditLink'

const token = 'q9Xx-3k_AbCdEfGhIjKlMnOpQrStUvWxYz0123456789'

describe('edit links', () => {
  it('keeps the token in the fragment, never the path or query', () => {
    const link = buildEditLink('CODE', token, 'https://go.example.com')
    const url = new URL(link)
    expect(url.pathname).toBe('/l/CODE/manage')
    expect(url.search).toBe('')
    expect(tokenFromHash(url.hash)).toBe(token)
  })

  it('round-trips through parseEditInput', () => {
    expect(parseEditInput(buildEditLink('CODE', token, 'https://go.example.com'))).toEqual({
      token,
      code: 'CODE',
    })
  })

  it('accepts a bare token', () => {
    expect(parseEditInput(`  ${token}  `)).toEqual({ token })
  })

  it('rejects links without a token and random text', () => {
    expect(parseEditInput('https://go.example.com/l/CODE/manage')).toBeNull()
    expect(parseEditInput('hello world')).toBeNull()
    expect(parseEditInput('')).toBeNull()
  })
})
