// The extension's core (task 11.2): connecting this browser to an account without a password
// (docs/v2/adr/ADR-020), and saving a page into a list from the popup.
import { cardTitle, createAccountList, signUpThroughApi, uniqueEmail } from '../fixtures'
import { connectFrom, expect, popupAbout, test, welcomePage } from './fixtures'

const ARTICLE = 'http://fixture.test/'

test('connect from the welcome page, then save a page to a new list', async ({ context, extensionId, page }) => {
  const email = uniqueEmail('ext')
  await signUpThroughApi(page, email)
  const welcome = await welcomePage(context)
  await expect(welcome.getByRole('heading', { level: 1 })).toHaveText('Save pages to your lists from any tab')

  // The site's page hears from the real content script that the extension asked, and names
  // the browser as the extension called it.
  const [site] = await Promise.all([
    context.waitForEvent('page'),
    welcome.getByRole('button', { name: 'Connect this browser' }).click(),
  ])
  await expect(site.getByRole('heading', { level: 1, name: 'Connect this browser?' })).toBeVisible()
  await expect(site.locator('dd')).toHaveText(['Chrome on Linux', email])
  await site.getByRole('button', { name: 'Connect', exact: true }).click()
  await expect(site.getByRole('heading', { level: 1, name: 'This browser is connected' })).toBeVisible()
  // The welcome page, still open, notices.
  await expect(welcome.getByRole('status')).toHaveText(`This browser is connected to ${email}.`)

  const popup = await popupAbout(context, extensionId, ARTICLE, 'An article worth keeping')
  await expect(popup.getByRole('textbox', { name: 'Title' })).toHaveValue('An article worth keeping')
  await expect(popup.getByText('You have no list you can add links to yet.')).toBeVisible()
  await expect(popup.getByRole('button', { name: 'Save', exact: true })).toBeDisabled()
  await popup.getByRole('button', { name: 'New list' }).click()
  await popup.getByRole('textbox', { name: "New list's name" }).fill('Reading')
  await popup.getByRole('button', { name: 'Create' }).click()
  await expect(popup.getByRole('radio', { name: /^Reading/ })).toBeChecked()
  await popup.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(popup.getByRole('status')).toHaveText('Saved to Reading.')

  // On the site: the list, private, with the page under the title from the popup.
  const [list] = await Promise.all([
    context.waitForEvent('page'),
    popup.getByRole('link', { name: 'Open the list' }).click(),
  ])
  await expect(list.getByRole('heading', { level: 1, name: 'Reading' })).toBeVisible()
  await expect(cardTitle(list, 'An article worth keeping')).toBeVisible()
  const code = new URL(list.url()).pathname.split('/')[2]
  const links = await (await page.request.get(`/api/v2/lists/${code}/links/`)).json()
  expect(links.results.map((link: { destination_url: string }) => link.destination_url)).toEqual([ARTICLE])
  await site.getByRole('link', { name: 'Connected browsers' }).click()
  await expect(site.getByText('Chrome on Linux')).toBeVisible()
})

test('the list saved to last comes first, and a page already there is reported', async ({
  context,
  extensionId,
  page,
}) => {
  await signUpThroughApi(page, uniqueEmail('ext-lists'))
  await createAccountList(page, 'Reading')
  await createAccountList(page, 'Work')
  await connectFrom(await welcomePage(context))

  const first = await popupAbout(context, extensionId, ARTICLE, 'First page')
  const lists = first.getByRole('radio')
  await expect(lists).toHaveCount(2)
  await expect(first.getByRole('radio', { name: /^Work/ })).not.toBeChecked() // nothing chosen yet
  await first.getByRole('radio', { name: /^Reading/ }).check()
  await first.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(first.getByRole('status')).toHaveText('Saved to Reading.')

  // Next time one action is enough: the list used last is first, and chosen.
  const second = await popupAbout(context, extensionId, `${ARTICLE}missing`, 'Second page')
  await expect(second.getByRole('radio').first()).toHaveAccessibleName(/^Reading/)
  await expect(second.getByRole('radio', { name: /^Reading/ })).toBeChecked()
  await second.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(second.getByRole('status')).toHaveText('Saved to Reading.')

  const again = await popupAbout(context, extensionId, ARTICLE, 'First page, again')
  await expect(again.getByRole('radio', { name: /^Reading/ })).toBeChecked()
  await again.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(again.getByRole('status')).toHaveText('This URL is already in the list.')
  await expect(again.getByRole('button', { name: 'Save', exact: true })).toBeVisible() // another list can be chosen
})

test("pages that can't be saved are explained", async ({ context, extensionId, page, baseURL }) => {
  await signUpThroughApi(page, uniqueEmail('ext-pages'))
  await connectFrom(await welcomePage(context))

  const settings = await popupAbout(context, extensionId, 'chrome://settings/', 'Settings')
  await expect(settings.getByRole('status')).toContainText('Only web pages (http and https) can be saved')
  await expect(settings.getByRole('button', { name: 'Save', exact: true })).toHaveCount(0)

  const own = await popupAbout(context, extensionId, `${baseURL}/lists`, 'My lists')
  await expect(own.getByRole('status')).toContainText("Pages of listlinkedin itself can't be saved")
})

test("a request the extension didn't start can't be approved", async ({ context, page }) => {
  await signUpThroughApi(page, uniqueEmail('ext-foreign'))
  await welcomePage(context) // the extension is installed, and asked for nothing

  // Someone sends a link to the Connect page with a challenge of their own.
  await page.goto(`/connect-browser?challenge=${'A'.repeat(43)}&name=Chrome%20on%20Linux`)
  await expect(
    page.getByRole('heading', { level: 1, name: "This request didn't come from your extension" }),
  ).toBeVisible()
  await expect(page.getByRole('button', { name: 'Connect', exact: true })).toHaveCount(0)
})

test('disconnecting on the site, or in the options, signs the extension out', async ({
  context,
  extensionId,
  page,
}) => {
  await signUpThroughApi(page, uniqueEmail('ext-out'))
  await connectFrom(await welcomePage(context))

  // On the site's account page.
  await page.goto('/account')
  await page.getByRole('button', { name: 'Disconnect Chrome on Linux' }).click()
  await page.getByRole('dialog', { name: 'Disconnect this browser?' }).getByRole('button', { name: 'Disconnect' }).click()
  await expect(page.getByText('No browsers are connected.')).toBeVisible()
  const popup = await popupAbout(context, extensionId, ARTICLE, 'A page')
  await expect(popup.getByRole('status')).toContainText('This browser was disconnected from your account')

  // Connected again from the popup, then disconnected in the extension's options.
  await connectFrom(popup)
  const options = await context.newPage()
  await options.goto(`chrome-extension://${extensionId}/options.html`)
  await expect(options.getByText('This browser is connected to')).toBeVisible()
  await options.getByRole('button', { name: 'Disconnect…' }).click()
  await options.getByRole('button', { name: 'Disconnect this browser' }).click()
  await expect(options.getByRole('button', { name: 'Connect this browser' })).toBeVisible()
  await page.reload()
  await expect(page.getByText('No browsers are connected.')).toBeVisible()
})
