// The extension's manifest (Manifest V3), one per browser. The pages and scripts are the
// same in both; what differs is how the background script is declared, and Firefox's add-on
// ID and data declaration.
import type { Site } from './site.ts'

export type Browser = 'chrome' | 'firefox'
export const BROWSERS: readonly Browser[] = ['chrome', 'firefox']

export interface ManifestOptions {
  version: string
  site: Site
  /** Firefox knows an add-on by this ID: its storage and permissions hang on it. */
  geckoId: string
}

const ICONS = {
  16: 'icons/icon-16.png',
  32: 'icons/icon-32.png',
  48: 'icons/icon-48.png',
  128: 'icons/icon-128.png',
}

export function manifestFor(browser: Browser, { version, site, geckoId }: ManifestOptions) {
  const common = {
    manifest_version: 3,
    name: 'listlinkedin',
    short_name: 'listlinkedin',
    version,
    description: 'Save pages to your listlinkedin lists and share them, without leaving the page.',
    icons: ICONS,
    action: {
      default_title: 'Save to listlinkedin',
      default_popup: 'popup.html',
      default_icon: ICONS,
    },
    options_ui: { page: 'options.html', open_in_tab: true },
    // activeTab: the page's address and title, only when the user opens the popup on it.
    permissions: ['storage', 'activeTab'],
    // The one site the extension talks to. Its content script only relays the Connect
    // page's messages (src/content/bridge.ts).
    host_permissions: [site.pattern],
    content_scripts: [{ matches: [site.pattern], js: ['content.js'], run_at: 'document_start' }],
  }
  if (browser === 'chrome')
    return {
      ...common,
      minimum_chrome_version: '120',
      background: { service_worker: 'background.js' },
    }
  return {
    ...common,
    // Firefox runs Manifest V3 background scripts as an event page, not a service worker.
    background: { scripts: ['background.js'] },
    browser_specific_settings: {
      gecko: {
        id: geckoId,
        // 140 is the first Firefox with the built-in data consent the next key relies on.
        strict_min_version: '140.0',
        // What leaves the browser, shown to the user at install: the address
        // (browsingActivity) and the title (websiteContent) of each page they save.
        data_collection_permissions: { required: ['browsingActivity', 'websiteContent'] },
      },
      // Not built for Firefox for Android, but if it is installed there: 142 is the first
      // with that consent (Mozilla's linter asks for the pair).
      gecko_android: { strict_min_version: '142.0' },
    },
  }
}
