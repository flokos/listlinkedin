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
  /**
   * Declare the optional permissions up front instead. Only for the build the end-to-end
   * tests load: a test can't answer the browser's question.
   */
  grantOptional?: boolean
}

/**
 * Asked for only when the picker first needs them (src/lib/permissions.ts): reading the open
 * tabs and the browsing history. Installing the extension asks for neither.
 */
export const OPTIONAL_PERMISSIONS = ['tabs', 'history']

const ICONS = {
  16: 'icons/icon-16.png',
  32: 'icons/icon-32.png',
  48: 'icons/icon-48.png',
  128: 'icons/icon-128.png',
}

/**
 * The keyboard shortcuts, as suggestions: the user can change each one in the browser's own
 * settings, and a browser leaves out a suggestion that is already taken. Alt+Shift with a
 * letter is what neither Chrome nor Firefox uses itself for L, D and C. The names are the
 * ones src/background/actions.ts answers to.
 */
export const COMMANDS = {
  _execute_action: {
    suggested_key: { default: 'Alt+Shift+L' },
    description: 'Open listlinkedin for this page',
  },
  'save-page': {
    suggested_key: { default: 'Alt+Shift+D' },
    description: 'Save this page to the list you saved to last',
  },
  'copy-list-link': {
    suggested_key: { default: 'Alt+Shift+C' },
    description: 'Copy the link of the list you saved to last',
  },
}

export function manifestFor(
  browser: Browser,
  { version, site, geckoId, grantOptional = false }: ManifestOptions,
) {
  const action = {
    default_title: 'Save to listlinkedin',
    default_popup: 'popup.html',
    default_icon: ICONS,
  }
  const common = {
    manifest_version: 3,
    name: 'listlinkedin',
    short_name: 'listlinkedin',
    version,
    description: 'Save pages to your listlinkedin lists and share them, without leaving the page.',
    icons: ICONS,
    options_ui: { page: 'options.html', open_in_tab: true },
    commands: COMMANDS,
    // The one site the extension talks to. Its content script only relays the Connect
    // page's messages (src/content/bridge.ts).
    host_permissions: [site.pattern],
    content_scripts: [{ matches: [site.pattern], js: ['content.js'], run_at: 'document_start' }],
  }
  // activeTab: the page's address and title, only when the user asks for it there (the
  //   popup, a right-click menu, a shortcut).
  // contextMenus: the right-click menus. clipboardWrite: copying a list's link from a
  //   shortcut or a menu, where there is no click in a page to allow it.
  const permissions = [
    'storage',
    'activeTab',
    'contextMenus',
    'clipboardWrite',
    ...(grantOptional ? OPTIONAL_PERMISSIONS : []),
  ]
  const optional = grantOptional ? {} : { optional_permissions: OPTIONAL_PERMISSIONS }
  if (browser === 'chrome')
    return {
      ...common,
      ...optional,
      action,
      // offscreen: the hidden document that copies for the service worker, which has no
      // clipboard of its own (src/lib/clipboard.ts).
      permissions: [...permissions, 'offscreen'],
      minimum_chrome_version: '120',
      background: { service_worker: 'background.js' },
    }
  return {
    ...common,
    ...optional,
    // Firefox would otherwise keep the button in its Extensions menu, where the mark that
    // says "saved" after a right-click or a shortcut can't be seen. The user can move it.
    action: { ...action, default_area: 'navbar' },
    permissions,
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
