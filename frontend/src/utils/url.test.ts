import { describe, expect, it } from 'vitest'

import { avatarFor, displayHost, displayUrl, validateUrl, withScheme } from './url'

describe('withScheme', () => {
  it('adds https to bare hosts and leaves schemes alone', () => {
    expect(withScheme('example.com/a')).toBe('https://example.com/a')
    expect(withScheme('  http://example.com ')).toBe('http://example.com')
    expect(withScheme('ftp://x.y')).toBe('ftp://x.y')
  })
})

describe('validateUrl (mirrors the server rules)', () => {
  it('accepts http and https links', () => {
    expect(validateUrl('https://example.com/article?x=1#y')).toBeNull()
    expect(validateUrl('http://bücher.example/')).toBeNull()
  })

  it.each([
    ['', /Enter a link/],
    ['not a url', /valid link/],
    ['ftp://example.com', /http and https/],
    ['javascript:alert(1)', /http and https/],
    ['https://user:pass@example.com', /username or password/],
    [`https://example.com/${'a'.repeat(2048)}`, /at most 2048/],
    [`${window.location.origin}/r/abc`, /this site/],
  ])('rejects %s', (input, message) => {
    expect(validateUrl(input)).toMatch(message)
  })
})

describe('display helpers', () => {
  it('shortens URLs for display', () => {
    expect(displayHost('https://www.Example.com/path')).toBe('example.com')
    expect(displayUrl('https://www.example.com/')).toBe('example.com')
    expect(displayUrl('https://example.com/a?b=1')).toBe('example.com/a?b=1')
  })

  it('gives a host a stable avatar', () => {
    const a = avatarFor('https://github.com/x')
    expect(a).toEqual(avatarFor('https://www.github.com/y'))
    expect(a.initial).toBe('G')
  })
})
