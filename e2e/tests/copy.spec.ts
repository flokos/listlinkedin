// "Make a copy" (roadmap 5.2; the copy step of scenario 1 in docs/v2/15-TEST-STRATEGY.md): the
// owner allows copies in the Share dialog, someone else copies the list into their own private
// list, which names its source. Signing out first, "Make a copy" asks to sign in and comes back.
import { type Page } from '@playwright/test'

import {
  apiAs,
  cardTitle,
  createAccountList,
  expect,
  otherDevice,
  signUpThroughApi,
  test,
  uniqueEmail,
} from './fixtures'

async function sharedList(page: Page) {
  await signUpThroughApi(page, uniqueEmail('source'))
  const { code } = await createAccountList(page, 'Dev tools')
  for (const url of ['https://example.com/docs', 'https://example.org/api']) {
    await apiAs(page, 'POST', `/api/v2/lists/${code}/links/`, { destination_url: url })
  }
  await apiAs(page, 'PATCH', `/api/v2/lists/${code}/`, { visibility: 'unlisted' }, 200)
  return code
}

async function makeCopy(page: Page, name?: string) {
  await page.getByRole('button', { name: 'List options' }).click()
  await page.getByRole('menuitem', { name: 'Make a copy…' }).click()
  const dialog = page.getByRole('dialog', { name: 'Make a copy' })
  const field = dialog.getByRole('textbox', { name: 'Name of the copy' })
  await expect(field).toHaveValue('Dev tools (copy)')
  if (name) await field.fill(name)
  await dialog.getByRole('button', { name: 'Make a copy' }).click()
}

test('the owner allows copies and someone else makes one', async ({ page, browser, baseURL }) => {
  test.slow() // two accounts on two devices
  const code = await sharedList(page)
  const friend = await otherDevice(browser, baseURL)
  await signUpThroughApi(friend.page, uniqueEmail('copier'))

  // Copies aren't allowed yet: a visitor's only list option is to report it (since 9.0).
  await friend.page.goto(`/l/${code}`)
  await expect(friend.page.getByRole('heading', { level: 1, name: 'Dev tools' })).toBeVisible()
  await friend.page.getByRole('button', { name: 'List options' }).click()
  await expect(friend.page.getByRole('menuitem')).toHaveText(['Report…'])
  await friend.page.keyboard.press('Escape')

  await page.goto(`/l/${code}`)
  await page.getByRole('button', { name: 'Share', exact: true }).click()
  const share = page.getByRole('dialog', { name: 'Share this list' })
  const allow = share.getByRole('switch', { name: 'Allow copies' })
  await expect(allow).not.toBeChecked()
  await allow.click()
  await expect(allow).toBeChecked()
  await expect(share).toContainText('Anyone who can see this list can make their own copy')

  await friend.page.reload()
  await makeCopy(friend.page, 'My tools')

  // The copy: the copier's own private list with the same links, naming its source.
  await expect(friend.page.getByRole('heading', { level: 1, name: 'My tools' })).toBeVisible()
  await expect(friend.page).not.toHaveURL(new RegExp(`/l/${code}`))
  await expect(friend.page.getByText('Your list', { exact: true })).toBeVisible()
  await expect(friend.page.getByText('Only people you add', { exact: true })).toBeVisible()
  await expect(cardTitle(friend.page, 'example.com')).toBeVisible()
  await expect(cardTitle(friend.page, 'example.org')).toBeVisible()
  const source = friend.page.getByRole('link', { name: 'Dev tools', exact: true })
  await expect(friend.page.getByText('Copied from')).toBeVisible()

  // Changing the copy leaves the original alone. (On phones the add form starts collapsed.)
  const addToggle = friend.page.getByRole('button', { name: 'Add a link' })
  if ((await addToggle.getAttribute('aria-expanded')) === 'false') await addToggle.click()
  await friend.page.getByRole('textbox', { name: 'Link', exact: true }).fill('https://example.net/')
  await friend.page.getByRole('button', { name: 'Add link' }).click()
  await expect(cardTitle(friend.page, 'example.net')).toBeVisible()
  await source.click()
  await expect(friend.page.getByRole('heading', { level: 1, name: 'Dev tools' })).toBeVisible()
  await expect(cardTitle(friend.page, 'example.org')).toBeVisible()
  await expect(cardTitle(friend.page, 'example.net')).toBeHidden()

  // Back from the original goes to the copy, not to the dialog.
  await friend.page.goBack()
  await expect(friend.page.getByRole('heading', { level: 1, name: 'My tools' })).toBeVisible()
  await expect(friend.page.getByRole('dialog', { name: 'Make a copy' })).toBeHidden()
  await friend.context.close()
})

test('signed out, making a copy asks to sign in and then offers it', async ({ page, browser, baseURL }) => {
  test.slow() // two devices
  const code = await sharedList(page)
  await apiAs(page, 'PATCH', `/api/v2/lists/${code}/`, { allow_fork: true }, 200)

  const visitor = await otherDevice(browser, baseURL)
  await visitor.page.goto(`/l/${code}`)
  await visitor.page.getByRole('button', { name: 'List options' }).click()
  await visitor.page.getByRole('menuitem', { name: 'Make a copy…' }).click()
  await expect(visitor.page).toHaveURL(/\/signin\?next=/)

  // Signed in (through the API here; auth.spec covers the form), the link comes back to the
  // dialog with the suggested name.
  await signUpThroughApi(visitor.page, uniqueEmail('visitor'))
  const next = new URL(visitor.page.url()).searchParams.get('next') ?? ''
  expect(next).toContain('dialog=copy')
  await visitor.page.goto(next)
  const dialog = visitor.page.getByRole('dialog', { name: 'Make a copy' })
  await expect(dialog.getByRole('textbox', { name: 'Name of the copy' })).toHaveValue('Dev tools (copy)')
  await dialog.getByRole('button', { name: 'Make a copy' }).click()
  await expect(visitor.page.getByRole('heading', { level: 1, name: 'Dev tools (copy)' })).toBeVisible()
  await visitor.context.close()
})
