// @vitest-environment node
import { describe, expect, it } from 'vitest'

import { COMMANDS, manifestFor } from './manifest.ts'
import { siteFrom } from './site.ts'

const options = {
  version: '1.2.3',
  site: siteFrom('https://lists.example.org'),
  geckoId: 'extension@lists.example.org',
}

describe('siteFrom', () => {
  it('turns a site address into its origin and match pattern', () => {
    expect(siteFrom('https://lists.example.org')).toEqual({
      origin: 'https://lists.example.org',
      pattern: 'https://lists.example.org/*',
    })
    // A pattern has no port: it covers the host on every port.
    expect(siteFrom('http://localhost:5173/')).toEqual({
      origin: 'http://localhost:5173',
      pattern: 'http://localhost/*',
    })
  })

  it('refuses anything but an https site (or localhost)', () => {
    for (const bad of [
      'lists.example.org',
      'http://lists.example.org',
      'https://lists.example.org/app',
      'https://lists.example.org/?a=1',
      'https://user:pw@lists.example.org',
      'ftp://lists.example.org',
    ])
      expect(() => siteFrom(bad), bad).toThrow(/LL_BASE_URL/)
  })
})

describe('manifestFor', () => {
  it('asks for the site and nothing more, in both browsers', () => {
    for (const browser of ['chrome', 'firefox'] as const) {
      const manifest = manifestFor(browser, options)
      expect(manifest.manifest_version).toBe(3)
      expect(manifest.version).toBe('1.2.3')
      // Nothing that reads tabs, history or pages; `offscreen` is Chrome's way to copy.
      expect(manifest.permissions).toEqual([
        'storage',
        'activeTab',
        'contextMenus',
        'clipboardWrite',
        ...(browser === 'chrome' ? ['offscreen'] : []),
      ])
      expect(manifest.host_permissions).toEqual(['https://lists.example.org/*'])
      // The content script runs on the site only, never on the pages people save.
      expect(manifest.content_scripts).toEqual([
        { matches: ['https://lists.example.org/*'], js: ['content.js'], run_at: 'document_start' },
      ])
      expect(manifest).not.toHaveProperty('optional_permissions')
      expect(manifest).not.toHaveProperty('content_security_policy')
    }
  })

  it('suggests shortcuts for the popup, saving and copying, the same in both browsers', () => {
    for (const browser of ['chrome', 'firefox'] as const)
      expect(manifestFor(browser, options).commands).toBe(COMMANDS)
    // The names are the ones the background script answers to (src/background/actions.ts).
    expect(Object.keys(COMMANDS)).toEqual(['_execute_action', 'save-page', 'copy-list-link'])
    const keys = Object.values(COMMANDS).map((command) => command.suggested_key.default)
    expect(new Set(keys).size).toBe(keys.length)
    for (const key of keys) expect(key).toMatch(/^Alt\+Shift\+[A-Z]$/)
  })

  it('puts the button on the toolbar in Firefox, where it would otherwise be in a menu', () => {
    expect(manifestFor('firefox', options).action).toMatchObject({
      default_popup: 'popup.html',
      default_area: 'navbar',
    })
    expect(manifestFor('chrome', options).action).not.toHaveProperty('default_area')
  })

  it('declares the background script the way each browser runs it', () => {
    const chrome = manifestFor('chrome', options)
    expect(chrome.background).toEqual({ service_worker: 'background.js' })
    expect(chrome).not.toHaveProperty('browser_specific_settings')

    const firefox = manifestFor('firefox', options)
    expect(firefox.background).toEqual({ scripts: ['background.js'] })
    expect(firefox).toHaveProperty('browser_specific_settings', {
      gecko: {
        id: 'extension@lists.example.org',
        strict_min_version: '140.0',
        // Firefox tells the user at install what the extension sends: the pages they save.
        data_collection_permissions: { required: ['browsingActivity', 'websiteContent'] },
      },
      gecko_android: { strict_min_version: '142.0' },
    })
    expect(firefox).not.toHaveProperty('minimum_chrome_version')
  })
})
