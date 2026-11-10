// @vitest-environment node
import { describe, expect, it } from 'vitest'

import { connectRequest, PAGE, pageMessage } from './bridge'

const challenge = 'c'.repeat(43)

describe('pageMessage', () => {
  it("accepts the Connect page's two messages and drops extra fields", () => {
    expect(pageMessage({ source: PAGE, type: 'hello', challenge, extra: 1 })).toEqual({
      source: PAGE,
      type: 'hello',
      challenge,
    })
    expect(pageMessage({ source: PAGE, type: 'code', challenge, code: 'abc' })).toEqual({
      source: PAGE,
      type: 'code',
      challenge,
      code: 'abc',
    })
  })

  it('ignores everything else', () => {
    for (const data of [
      null,
      'hello',
      { type: 'hello', challenge },
      { source: 'someone-else', type: 'hello', challenge },
      { source: PAGE, type: 'hello', challenge: 'short' },
      { source: PAGE, type: 'hello', challenge: `${challenge}!` },
      { source: PAGE, type: 'code', challenge },
      { source: PAGE, type: 'code', challenge, code: 'x'.repeat(129) },
      { source: PAGE, type: 'other', challenge },
    ])
      expect(pageMessage(data), JSON.stringify(data)).toBeNull()
  })
})

describe('connectRequest', () => {
  it('accepts what the content script asks, and nothing else', () => {
    expect(connectRequest({ type: 'connect:started', challenge })).toEqual({
      type: 'connect:started',
      challenge,
    })
    expect(connectRequest({ type: 'connect:code', challenge, code: 'abc' })).toEqual({
      type: 'connect:code',
      challenge,
      code: 'abc',
    })
    expect(connectRequest({ type: 'connect:code', challenge })).toBeNull()
    expect(connectRequest({ type: 'connect:started', challenge: 'x' })).toBeNull()
    expect(connectRequest({ type: 'disconnect', challenge })).toBeNull()
    expect(connectRequest(undefined)).toBeNull()
  })
})
