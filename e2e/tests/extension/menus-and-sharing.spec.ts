// The extension's menus, shortcuts and sharing (task 11.3): looking into a list and sharing it
// from the popup, and what a right-click entry and a keyboard shortcut do.
//
// Playwright can't open a browser's own menus or press an extension's shortcut, so those two
// are fired the way the browser fires them: on the service worker's own events. What reaches
// the page (the menu as it is drawn, the keys as they are bound) is checked by hand
// (docs/qa-checklist.md).
import type { BrowserContext, Page, Worker } from '@playwright/test'

import { apiAs, createAccountList, signUpThroughApi, uniqueEmail } from '../fixtures'
import { connectFrom, expect, popupAbout, test, welcomePage } from './fixtures'

const ARTICLE = 'http://fixture.test/'

// The extension API inside the service worker (this project has no types for it). `dispatch`
// fires an event as the browser does.
declare const chrome: any

/** What the system clipboard holds, read by the site's page (an extension page can't). */
async function clipboard(page: Page): Promise<string> {
  await page.bringToFront()
  return page.evaluate(() => navigator.clipboard.readText())
}

const worker = (context: BrowserContext): Worker => context.serviceWorkers()[0]!

const linksOf = async (page: Page, code: string): Promise<{ destination_url: string; title: string | null }[]> =>
  (await (await page.request.get(`/api/v2/lists/${code}/links/`)).json()).results

test('look into a list, copy its link, choose who can open it and add it to a group', async ({
  context,
  extensionId,
  page,
  request,
}) => {
  await signUpThroughApi(page, uniqueEmail('ext-share'))
  const list = await createAccountList(page, 'Reading')
  await apiAs(page, 'POST', `/api/v2/lists/${list.code}/links/`, { destination_url: ARTICLE, title: 'An article' })
  const group = await apiAs(page, 'POST', '/api/v2/groups/', { title: 'Team' })
  await page.goto('/')
  await context.grantPermissions(['clipboard-read', 'clipboard-write'])
  await connectFrom(await welcomePage(context))

  const popup = await popupAbout(context, extensionId, ARTICLE, 'An article')
  await popup.getByRole('button', { name: 'My lists' }).click()
  await popup.getByRole('button', { name: /^Reading/ }).click()
  await expect(popup.getByRole('heading', { level: 2, name: 'Reading' })).toBeVisible()
  await expect(popup.getByRole('link', { name: 'An article' })).toHaveAttribute('href', ARTICLE)

  // Copying the link shares nothing: the list is as private as before.
  await popup.getByRole('button', { name: 'Copy link', exact: true }).click()
  await expect(popup.getByRole('status')).toHaveText('Link copied. Only people you add can open this link.')
  const { url } = await (await page.request.get(`/api/v2/lists/${list.code}/`)).json()
  expect(await clipboard(page)).toBe(url)
  expect((await request.get(`/api/v2/lists/${list.code}/`)).status()).toBe(404)

  // Who can open it changes when the user says so, and only then.
  await popup.bringToFront()
  await popup.getByLabel('Who can open it').selectOption({ label: 'Anyone with the link' })
  expect((await request.get(`/api/v2/lists/${list.code}/`)).status()).toBe(404)
  await popup.getByRole('button', { name: 'Change', exact: true }).click()
  await expect(popup.getByRole('status')).toHaveText(
    'Changed. Anyone with this link can view the list, but not change it.',
  )
  expect((await request.get(`/api/v2/lists/${list.code}/`)).status()).toBe(200)

  await popup.getByLabel('Add to a group').selectOption({ label: 'Team' })
  await popup.getByRole('button', { name: 'Add', exact: true }).click()
  await expect(popup.getByRole('status')).toHaveText('Added to the group “Team”.')
  const inGroup = await (await page.request.get(`/api/v2/groups/${group.code}/lists/`)).json()
  expect(inGroup.map((item: { code: string }) => item.code)).toEqual([list.code])

  // The group's own link, from the list of lists.
  await popup.getByRole('button', { name: 'All lists' }).click()
  const myLists = popup.getByRole('region', { name: 'My lists' })
  await myLists.getByLabel('Show lists from').selectOption({ label: 'Group: Team' })
  await expect(myLists.getByRole('button', { name: /^Reading/ })).toBeVisible()
  await popup.getByRole('button', { name: 'Copy group link' }).click()
  await expect(popup.getByRole('status')).toHaveText('Group link copied. Only people you add can open this link.')
  expect(await clipboard(page)).toBe(group.url)
})

test('a right-click entry saves without a window, and a shortcut copies the list link', async ({
  context,
  extensionId,
  page,
}) => {
  await signUpThroughApi(page, uniqueEmail('ext-menus'))
  const list = await createAccountList(page, 'Reading')
  await page.goto('/')
  await context.grantPermissions(['clipboard-read', 'clipboard-write'])
  await connectFrom(await welcomePage(context))

  // Saving once from the popup makes "Reading" the list saved to last.
  const popup = await popupAbout(context, extensionId, ARTICLE, 'From the popup')
  await popup.getByRole('radio', { name: /^Reading/ }).check()
  await popup.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(popup.getByRole('status')).toHaveText('Saved to Reading.')
  await popup.close()

  // "Save to listlinkedin ▸ Reading" on a page: saved under the tab's title, and the button says so.
  const pageUrl = `${ARTICLE}right-clicked`
  await worker(context).evaluate(
    ([menuItemId, url]) =>
      chrome.contextMenus.onClicked.dispatch({ menuItemId, pageUrl: url }, { url, title: 'Right-clicked' }),
    [`save-to:${list.code}`, pageUrl],
  )
  await expect.poll(async () => (await linksOf(page, list.code)).map((link) => link.destination_url)).toEqual([
    ARTICLE,
    pageUrl,
  ])
  expect((await linksOf(page, list.code))[1]!.title).toBe('Right-clicked')
  expect(await worker(context).evaluate(() => chrome.action.getBadgeText({}))).toBe('✓')

  // The same page again: the site refuses, the button shows it, and the popup says why once.
  await worker(context).evaluate(
    ([menuItemId, url]) =>
      chrome.contextMenus.onClicked.dispatch({ menuItemId, pageUrl: url }, { url, title: 'Right-clicked' }),
    [`save-to:${list.code}`, pageUrl],
  )
  await expect.poll(() => worker(context).evaluate(() => chrome.action.getBadgeText({}))).toBe('!')
  const told = await popupAbout(context, extensionId, ARTICLE, 'From the popup')
  await expect(told.getByRole('status').first()).toContainText("fixture.test/right-clicked wasn't saved to “Reading”.")
  await expect.poll(() => worker(context).evaluate(() => chrome.action.getBadgeText({}))).toBe('')
  await told.close()

  // The copy shortcut: Chrome's service worker has no clipboard, so this goes through the
  // offscreen document.
  await worker(context).evaluate(() => chrome.commands.onCommand.dispatch('copy-list-link'))
  const { url } = await (await page.request.get(`/api/v2/lists/${list.code}/`)).json()
  await expect.poll(() => clipboard(page)).toBe(url)

  // "Choose a list…" on a link: a small window about the link, not about the tab in front.
  const linked = `${ARTICLE}linked`
  const [chooser] = await Promise.all([
    context.waitForEvent('page'),
    worker(context).evaluate(
      ([url, linkUrl]) =>
          chrome.contextMenus.onClicked.dispatch({ menuItemId: 'choose', pageUrl: url, linkUrl }, { url, title: 'A page' }),
      [ARTICLE, linked],
    ),
  ])
  await expect(chooser.getByText(linked)).toBeVisible()
  await expect(chooser.getByRole('textbox', { name: 'Title' })).toHaveValue('') // the linked page's own, later
  // The first window to open since the copy says what was worth knowing about it: the list is private.
  await expect(chooser.getByRole('status')).toHaveText(
    'You copied the link to “Reading”. Only people you add can open this link.',
  )
  await chooser.getByRole('button', { name: 'Save', exact: true }).click() // Reading is chosen already
  await expect(chooser.getByText('Saved to Reading.')).toBeVisible()
  expect((await linksOf(page, list.code)).map((link) => link.destination_url)).toContain(linked)
})

test("put a list's links in another order and remove one, from the popup", async ({ context, extensionId, page }) => {
  await signUpThroughApi(page, uniqueEmail('ext-edit'))
  const list = await createAccountList(page, 'Reading')
  for (const name of ['one', 'two', 'three'])
    await apiAs(page, 'POST', `/api/v2/lists/${list.code}/links/`, { destination_url: `${ARTICLE}${name}`, title: name })
  await page.goto('/')
  await connectFrom(await welcomePage(context))
  const titles = async () => (await linksOf(page, list.code)).map((link) => link.title)
  const revisions = async () => {
    const answer = await (await page.request.get(`/api/v2/lists/${list.code}/revisions/`)).json()
    return (answer.results ?? answer).length
  }
  const before = await revisions()

  const popup = await popupAbout(context, extensionId, ARTICLE, 'An article')
  await popup.getByRole('button', { name: 'My lists' }).click()
  await popup.getByRole('button', { name: /^Reading/ }).click()
  await expect(popup.getByRole('button', { name: 'Move three up' })).toHaveCount(0) // not before it is asked for
  await popup.getByRole('button', { name: 'Edit links' }).click()

  // One place up, by the keyboard: the button keeps the focus, so Enter moves it again.
  await popup.getByRole('button', { name: 'Move three up' }).focus()
  await popup.keyboard.press('Enter')
  await expect(popup.getByRole('status')).toHaveText('“three” is now 2 of 3.')
  await expect(popup.getByRole('button', { name: 'Move three up' })).toBeFocused()
  await popup.keyboard.press('Enter')
  await expect(popup.getByRole('status')).toHaveText('“three” is now 1 of 3.')
  expect(await titles()).toEqual(['three', 'one', 'two'])
  expect(await revisions()).toBe(before + 2) // each move is one change in the history

  // By dragging: a row dropped on another takes its place.
  const row = (title: string) => popup.locator('.detail__link').filter({ hasText: title })
  await row('two').dragTo(row('three'))
  await expect(popup.getByRole('status')).toHaveText('“two” is now 1 of 3.')
  expect(await titles()).toEqual(['two', 'three', 'one'])
  expect(await revisions()).toBe(before + 3)

  // Removing asks first, in the row.
  await popup.getByRole('button', { name: 'Remove one…' }).click()
  await popup.getByRole('button', { name: 'Keep' }).click()
  expect(await titles()).toEqual(['two', 'three', 'one'])
  await popup.getByRole('button', { name: 'Remove one…' }).click()
  await popup.getByRole('button', { name: 'Remove one from the list' }).click()
  await expect(popup.getByRole('status')).toContainText('Removed “one”.')
  expect(await titles()).toEqual(['two', 'three'])
  expect(await revisions()).toBe(before + 4)
  await expect(popup.getByText('2 links')).toBeVisible()
})
