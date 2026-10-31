import { cardTitle, expect, openAsOwner, otherDevice, test } from './fixtures'

test('visitors see the list but no owner controls', async ({ page, api }) => {
  const list = await api.createList('Visitor view')
  await api.addLink(list, 'https://example.com/a', 'First link')
  await page.goto(`/l/${list.public_code}`)
  await expect(page.getByText('Shared list', { exact: true })).toBeVisible()
  await expect(cardTitle(page, 'First link')).toBeVisible()
  await expect(page.getByText('Add a link')).toBeHidden()
  // Visitors' only list option is to report the list to the operator (since 9.0).
  await page.getByRole('button', { name: 'List options' }).click()
  await expect(page.getByRole('menuitem')).toHaveText(['Report…'])
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: 'Rename list' })).toBeHidden()
  // Visitors get the link's menu (open, copy, details), without editing.
  await page.getByRole('button', { name: 'More actions for First link' }).click()
  await expect(page.getByRole('menuitem', { name: 'Details' })).toBeVisible()
  await expect(page.getByRole('menuitem', { name: 'Edit' })).toBeHidden()
  await expect(page.getByRole('menuitem', { name: 'Delete' })).toBeHidden()
})

// V1's edit links were retired in v2.1.0 (task 9.6): an old one opens the list read-only, and
// its secret never stays in the address bar. Editing is the owner's account's.
test('an old edit link opens the list without keeping its secret', async ({ page, api }) => {
  const list = await api.createList('Old edit link')
  await page.goto(`/l/${list.public_code}/manage#t=an-old-owner-token-0000000000000000`)
  await expect(page).toHaveURL(`/l/${list.public_code}`)
  expect(await page.evaluate(() => location.hash)).toBe('')
  await expect(page.getByRole('heading', { level: 1, name: 'Old edit link' })).toBeVisible()
  await expect(page.getByText('Shared list', { exact: true })).toBeVisible()
  await expect(page.getByText('Add a link')).toBeHidden()
})

test("signing in as the owner unlocks editing on any device", async ({ page, api, browser, baseURL }) => {
  const list = await api.createList('Mine everywhere')
  await openAsOwner(page, list)
  await expect(page.getByRole('button', { name: 'Rename list' })).toBeVisible()

  const laptop = await otherDevice(browser, baseURL)
  await laptop.page.goto(`/l/${list.public_code}`)
  await expect(laptop.page.getByText('Shared list', { exact: true })).toBeVisible()
  await openAsOwner(laptop.page, list)
  await expect(laptop.page.getByRole('button', { name: 'Rename list' })).toBeVisible()
  await laptop.context.close()
})

test('renaming and deleting a list', async ({ page, api }) => {
  const list = await api.createList('Old name')
  await openAsOwner(page, list)
  await page.getByRole('button', { name: 'Rename list' }).click()
  await page.getByRole('textbox', { name: 'List name' }).fill('New name')
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { level: 1, name: 'New name' })).toBeVisible()
  await expect(page).toHaveTitle('New name · listlinkedin')

  await page.getByRole('button', { name: 'List options' }).click()
  await page.getByRole('menuitem', { name: 'Delete list' }).click()
  const confirm = page.getByRole('button', { name: 'Delete list' })
  await expect(confirm).toBeDisabled()
  await page.getByRole('textbox', { name: /Type/ }).fill('New name')
  await confirm.click()
  await expect(page).toHaveURL('/lists')
  await expect(page.getByText('List deleted')).toBeVisible()
  await page.goto(`/l/${list.public_code}`)
  await expect(page.getByRole('heading', { name: "This list doesn't exist" })).toBeVisible()
})
