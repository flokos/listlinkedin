// Every test starts with a new fake browser as `chrome`, and no leftover `fetch` mock.
import { afterEach, beforeEach, vi } from 'vitest'

import { installFakeBrowser } from './fakeBrowser'

beforeEach(() => {
  installFakeBrowser()
})

afterEach(() => {
  vi.unstubAllGlobals()
})
