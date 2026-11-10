// PKCE (RFC 7636), S256: the extension keeps a random verifier and shows the site only its
// SHA-256, the challenge. The one-time code the site hands back is useless without the
// verifier, so nothing else that hears the code can connect (docs/v2/adr/ADR-020).

function base64url(bytes: Uint8Array): string {
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/** base64url(SHA-256(verifier)), without padding: 43 characters. */
export async function challengeFor(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))
  return base64url(new Uint8Array(digest))
}

/** A new verifier (256 random bits, 43 characters) and its challenge. */
export async function newPkce(): Promise<{ verifier: string; challenge: string }> {
  const verifier = base64url(crypto.getRandomValues(new Uint8Array(32)))
  return { verifier, challenge: await challengeFor(verifier) }
}
