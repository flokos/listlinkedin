// The browser extension, run for real: Chromium with extension/ loaded (run.sh builds it for
// this stack's address and mounts it at /extension), against the production stack.
//
// Chromium loads extensions only into a persistent context, and headless only through the
// `chromium` channel, so these tests bring their own browser instead of the project's.
// What can't be driven from here is checked by hand (docs/qa-checklist.md): the toolbar
// popup as a popup (the tests open popup.html as a page, about an address in its query),
// right-click menus, keyboard shortcuts, permission prompts, and Firefox altogether.
import { type BrowserContext, chromium, expect, type Page, test as base } from '@playwright/test'

const EXTENSION = process.env.E2E_EXTENSION ?? '/extension'

// Refusals the extension and the app handle on purpose still reach the console in Chromium.
const EXPECTED_CONSOLE = [/status of (400|401|403|404|409|410|429)/, /Failed to load resource/]

export const test = base.extend<{
  context: BrowserContext
  page: Page
  /** The loaded extension's ID: its pages are at chrome-extension://{id}/. */
  extensionId: string
  consoleErrors: string[]
}>({
  context: async ({ baseURL, locale, timezoneId, viewport }, use) => {
    const context = await chromium.launchPersistentContext('', {
      channel: 'chromium',
      baseURL,
      locale,
      timezoneId,
      viewport,
      ignoreHTTPSErrors: true,
      args: [
        `--disable-extensions-except=${EXTENSION}`,
        `--load-extension=${EXTENSION}`,
        // The extension's own requests meet the stack's throwaway certificate too.
        '--ignore-certificate-errors',
      ],
    })
    await use(context)
    await context.close()
  },

  extensionId: async ({ context }, use) => {
    const worker = context.serviceWorkers()[0] ?? (await context.waitForEvent('serviceworker'))
    await use(new URL(worker.url()).host)
  },

  // A tab for the site, next to the welcome page the extension opens when it is installed.
  page: async ({ context }, use) => use(await context.newPage()),

  // Every tab of the test, the extension's pages included, must stay free of console errors.
  consoleErrors: [
    async ({ context }, use) => {
      const errors: string[] = []
      const watch = (page: Page) => {
        page.on('console', (message) => {
          if (message.type() !== 'error') return
          if (EXPECTED_CONSOLE.some((expected) => expected.test(message.text()))) return
          errors.push(`${page.url()}: ${message.text()}`)
        })
        page.on('pageerror', (error) => errors.push(`${page.url()}: Uncaught: ${error.message}`))
      }
      context.pages().forEach(watch)
      context.on('page', watch)
      await use(errors)
      expect(errors, 'unexpected console errors').toEqual([])
    },
    { auto: true },
  ],
})

export { expect }

/** The welcome page, which the extension opens by itself when it is installed. */
export async function welcomePage(context: BrowserContext): Promise<Page> {
  const find = () => context.pages().find((page) => page.url().endsWith('/welcome.html'))
  await expect.poll(() => find() !== undefined, 'the extension opens its welcome page').toBe(true)
  return find()!
}

/**
 * Chooses "Connect this browser" on one of the extension's pages and approves the request on
 * the site, as the user signed in there. Returns the site's tab, on "This browser is connected".
 */
export async function connectFrom(extensionPage: Page): Promise<Page> {
  const context = extensionPage.context()
  const [site] = await Promise.all([
    context.waitForEvent('page'),
    extensionPage.getByRole('button', { name: 'Connect this browser' }).click(),
  ])
  await expect(site.getByRole('heading', { level: 1, name: 'Connect this browser?' })).toBeVisible()
  await site.getByRole('button', { name: 'Connect', exact: true }).click()
  await expect(site.getByRole('heading', { level: 1, name: 'This browser is connected' })).toBeVisible()
  return site
}

/** Opens the popup as a page about `url`: what the toolbar button shows for the tab in front. */
export async function popupAbout(context: BrowserContext, extensionId: string, url: string, title: string) {
  const popup = await context.newPage()
  const query = new URLSearchParams({ url, title })
  await popup.goto(`chrome-extension://${extensionId}/popup.html?${query}`)
  return popup
}
