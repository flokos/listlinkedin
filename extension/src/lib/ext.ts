// The WebExtensions API: `browser` in Firefox, `chrome` in Chrome. In Manifest V3 both return
// promises, so one code path serves both. Looked up on every call, so tests can install a fake.

type Api = typeof chrome

export function ext(): Api {
  const scope = globalThis as unknown as { browser?: Api; chrome?: Api }
  const api = scope.browser?.runtime ? scope.browser : scope.chrome
  if (!api?.runtime) throw new Error('The extension API is not available here.')
  return api
}
