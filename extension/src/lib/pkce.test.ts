// @vitest-environment node
import { describe, expect, it } from 'vitest'

import { challengeFor, newPkce } from './pkce'

describe('PKCE', () => {
  it('makes the S256 challenge of RFC 7636 (its appendix B example)', async () => {
    expect(await challengeFor('dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk')).toBe(
      'E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM',
    )
  })

  it('makes a new verifier each time, in the shape the site accepts', async () => {
    const first = await newPkce()
    const second = await newPkce()
    expect(first.verifier).toMatch(/^[A-Za-z0-9_-]{43}$/)
    expect(first.challenge).toMatch(/^[A-Za-z0-9_-]{43}$/)
    expect(first.challenge).toBe(await challengeFor(first.verifier))
    expect(second.verifier).not.toBe(first.verifier)
  })
})
