// @vitest-environment node
// public/extension-updates.json is what an installed Firefox add-on reads to learn that a
// newer version exists (its manifest's update_url, ADR-023). It is written by hand, so this
// keeps it in step with the version the site offers.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { EXTENSION_VERSION, extensionDownloads } from './extensionDownloads'

const file = fileURLToPath(new URL('../../public/extension-updates.json', import.meta.url))
const manifest = JSON.parse(readFileSync(file, 'utf8')) as {
  addons: Record<string, { updates: { version: string; update_link: string }[] }>
}

describe('extension-updates.json', () => {
  it('offers the add-on, by its ID, exactly the version the Browser extension page offers', () => {
    // The ID in extension/scripts/build.ts: Firefox looks its own up and ignores the rest.
    expect(Object.keys(manifest.addons)).toEqual(['extension@listlinkedin.versioncontrol.xyz'])
    const { updates } = manifest.addons['extension@listlinkedin.versioncontrol.xyz']!
    expect(updates).toEqual([
      { version: EXTENSION_VERSION, update_link: extensionDownloads.firefox },
    ])
  })

  it('sends Firefox to a file signed by Mozilla, over https', () => {
    expect(extensionDownloads.firefox).toMatch(/^https:\/\/.+-firefox-signed\.xpi$/)
  })
})
