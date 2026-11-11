// Saving several pages at once (task 11.5): the picker, from the open tabs and from the
// history, through the batch endpoint (11.4).
//
// The build these tests load declares the `tabs` and `history` permissions up front
// (run.sh: LL_GRANT_OPTIONAL), because a test can't answer the browser's question. Asking
// for them, and taking them back, is covered by unit tests and checked by hand
// (docs/qa-checklist.md).
import type { Page } from '@playwright/test'

import { signUpThroughApi, uniqueEmail } from '../fixtures'
import { connectFrom, expect, test, welcomePage } from './fixtures'

// The extension API inside the service worker (this project has no types for it).
declare const chrome: any

const SITE = 'http://fixture.test/'

const listsOf = async (
  page: Page,
): Promise<{ code: string; title: string; link_count: number; visibility: string }[]> =>
  (await (await page.request.get('/api/v2/lists/')).json()).results

const linksOf = async (page: Page, code: string): Promise<{ destination_url: string; title: string | null }[]> =>
  (await (await page.request.get(`/api/v2/lists/${code}/links/`)).json()).results

test('save the open tabs to a new list, then pick from the history', async ({ context, extensionId, page }) => {
  await signUpThroughApi(page, uniqueEmail('ext-tabs'))
  await page.goto('/')
  await connectFrom(await welcomePage(context))

  // The browser can't reach the fixture site by this name (only the API's fetcher can), so
  // the pages are served here. Each says its address in its title.
  await context.route(`${SITE}**`, (route) => {
    const { search } = new URL(route.request().url())
    return route.fulfill({ contentType: 'text/html', body: `<title>Fixture ${search}</title><p>A page.</p>` })
  })

  // Two ordinary tabs, next to the site's own and the extension's pages.
  const first = await context.newPage()
  await first.goto(SITE)
  const second = await context.newPage()
  await second.goto(`${SITE}?second`)

  const picker = await context.newPage()
  await picker.goto(`chrome-extension://${extensionId}/picker.html?source=tabs`)
  await expect(picker.getByRole('heading', { level: 1 })).toHaveText('Save several pages')
  // Only what can be saved: not the site itself, not the extension's pages.
  const pages = picker.locator('.picker__url')
  await expect(pages).toHaveText([SITE, `${SITE}?second`])

  await picker.getByLabel(/^Select all/).check()
  await expect(picker.getByLabel('Save to')).toHaveValue('+new') // no list yet
  await picker.getByLabel("New list's name").fill('From my tabs')
  // A new list is private unless the user says otherwise, here.
  await expect(picker.getByLabel('Who can open it')).toHaveValue('private')
  await picker.getByLabel('Who can open it').selectOption('unlisted')
  await picker.getByRole('button', { name: 'Save 2 pages' }).click()
  await expect(picker.getByRole('status')).toContainText('2 pages saved.')

  const [list] = await listsOf(page)
  expect(list).toMatchObject({ title: 'From my tabs', link_count: 2, visibility: 'unlisted' })
  expect(await linksOf(page, list!.code)).toMatchObject([
    { destination_url: SITE, title: 'Fixture' }, // the tabs' titles, as the user saw them
    { destination_url: `${SITE}?second`, title: 'Fixture ?second' },
  ])
  // One change in the list's history, not one per page.
  const revisions = await (await page.request.get(`/api/v2/lists/${list!.code}/revisions/`)).json()
  expect(revisions.results ?? revisions).toHaveLength(2) // created, then the two pages

  // The history has the pages that were visited; the list is offered first now.
  await second.goto(`${SITE}?third`)
  await picker.bringToFront()
  await picker.getByRole('button', { name: 'History' }).click()
  await expect(picker.locator('.picker__url').filter({ hasText: `${SITE}?third` })).toBeVisible()
  await expect(picker.getByLabel('Save to')).toHaveValue(list!.code)
  await picker.getByLabel('Search your history').fill('third')
  await expect(picker.locator('.picker__url')).toHaveText([`${SITE}?third`])
  await picker.getByLabel('Search your history').fill('fixture')
  await expect(picker.locator('.picker__url').filter({ hasText: `${SITE}?second` })).toBeVisible()
  await picker.getByLabel(/^Select all/).check()
  await picker.getByRole('button', { name: /^Save \d+ pages$/ }).click()
  // The two from before are skipped, and said so.
  await expect(picker.getByRole('status')).toContainText('1 page saved, 2 were already there.')
  expect((await linksOf(page, list!.code)).map((link) => link.destination_url)).toEqual([
    SITE,
    `${SITE}?second`,
    `${SITE}?third`,
  ])
})

test('the popup leads to the picker', async ({ context, extensionId, page }) => {
  await signUpThroughApi(page, uniqueEmail('ext-picker'))
  await page.goto('/')
  await connectFrom(await welcomePage(context))

  const popup = await context.newPage()
  await popup.goto(`chrome-extension://${extensionId}/popup.html?url=${encodeURIComponent(SITE)}&title=x`)
  const [picker] = await Promise.all([
    context.waitForEvent('page'),
    popup.getByRole('link', { name: 'from history' }).click(),
  ])
  await expect(picker.getByRole('button', { name: 'History' })).toHaveAttribute('aria-pressed', 'true')
})

test('the right-click menu leads to the picker', async ({ context, page }) => {
  await signUpThroughApi(page, uniqueEmail('ext-picker-menu'))
  await page.goto('/')
  await connectFrom(await welcomePage(context))
  const [worker] = context.serviceWorkers()

  // Under "Save to listlinkedin" on a page, and on the toolbar button (its ids end in ":button").
  for (const [menuItemId, source] of [
    ['several:tabs', 'Open tabs'],
    ['several:history:button', 'History'],
  ] as const) {
    const [picker] = await Promise.all([
      context.waitForEvent('page'),
      worker!.evaluate(
        (id) => chrome.contextMenus.onClicked.dispatch({ menuItemId: id, pageUrl: 'http://fixture.test/' }),
        menuItemId,
      ),
    ])
    await expect(picker.getByRole('button', { name: source })).toHaveAttribute('aria-pressed', 'true')
    await picker.close()
  }
})
