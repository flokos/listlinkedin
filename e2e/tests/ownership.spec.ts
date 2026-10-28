import { cardTitle, editLinkFor, expect, openAsOwner, otherDevice, test } from './fixtures'

test('visitors see the list but no owner controls', async ({ page, api }) => {
  const list = await api.createList('Visitor view')
  await api.addLink(list, 'https://example.com/a', 'First link')
  await page.goto(`/l/${list.public_code}`)
  await expect(page.getByText('Shared list', { exact: true })).toBeVisible()
  await expect(cardTitle(page, 'First link')).toBeVisible()
  await expect(page.getByText('Add a link')).toBeHidden()
  await expect(page.getByRole('button', { name: 'List options' })).toBeHidden()
  await expect(page.getByRole('button', { name: 'Rename list' })).toBeHidden()
  await expect(page.getByRole('button', { name: /More actions for/ })).toBeHidden()
})

test('the edit link unlocks editing and never stays in the address bar', async ({ page, api }) => {
  const list = await api.createList('Unlock me')
  await page.goto(editLinkFor(list))
  await expect(page).toHaveURL(`/l/${list.public_code}`)
  expect(await page.evaluate(() => location.hash)).toBe('')
  await expect(page.getByText('Your list', { exact: true })).toBeVisible()
  await expect(page.getByText('Editing unlocked on this device')).toBeVisible()
  // Going back must not land on a URL that still carries the token.
  const history = await page.evaluate(() => history.length)
  if (history > 1) {
    await page.goBack()
    expect(page.url()).not.toContain('#t=')
  }
})

test('a wrong or incomplete edit link explains itself', async ({ page, api }) => {
  const list = await api.createList('Wrong token')
  await page.goto(`/l/${list.public_code}/manage#t=not-the-right-token-at-all-0000`)
  await expect(page.getByRole('heading', { name: 'This edit link no longer works' })).toBeVisible()
  await page.goto(`/l/${list.public_code}/manage`)
  await expect(page.getByRole('heading', { name: 'This edit link is incomplete' })).toBeVisible()
})

test('replacing the edit link locks out other devices until they get the new one', async ({
  page,
  browser,
  baseURL,
  api,
}) => {
  const list = await api.createList('Rotate me')
  await openAsOwner(page, list)
  const laptop = await otherDevice(browser, baseURL)
  await openAsOwner(laptop.page, list)

  // Device A replaces the edit link.
  await page.getByRole('button', { name: 'List options' }).click()
  await page.getByRole('menuitem', { name: 'Replace edit link' }).click()
  await page.getByRole('button', { name: 'Replace edit link' }).click()
  const reveal = page.getByRole('dialog', { name: 'Here is your new edit link' })
  await expect(reveal).toBeVisible()
  const newLink = await reveal.getByRole('textbox', { name: 'Private edit link' }).inputValue()
  expect(newLink).not.toContain(list.owner_token)
  await reveal.getByRole('checkbox', { name: /saved my edit link/ }).check()
  await reveal.getByRole('button', { name: 'Done' }).click()

  // Device B's next change is refused and explained; the rename editor closes.
  const b = laptop.page
  await b.getByRole('button', { name: 'Rename list' }).click()
  await b.getByRole('textbox', { name: 'List name' }).fill('Hijacked')
  await b.getByRole('button', { name: 'Save name' }).click()
  await expect(b.getByText('Your edit link was replaced')).toBeVisible()
  await expect(b.getByRole('textbox', { name: 'List name' })).toBeHidden()
  await expect(b.getByRole('heading', { level: 1, name: 'Rotate me' })).toBeVisible()

  // Pasting the new edit link restores access.
  await b.getByRole('button', { name: 'Paste edit link' }).click()
  await b.getByRole('textbox', { name: 'Edit link' }).fill(newLink)
  await b.getByRole('button', { name: 'Unlock editing' }).click()
  await expect(b.getByText('Your edit link was replaced')).toBeHidden()
  await expect(b.getByText('Your list', { exact: true })).toBeVisible()
  await laptop.context.close()
})

test('forgetting a list removes edit access from this device only', async ({ page, api }) => {
  const list = await api.createList('Forget me')
  await openAsOwner(page, list)
  await page.getByRole('button', { name: 'List options' }).click()
  await page.getByRole('menuitem', { name: 'Forget on this device' }).click()
  await expect(page.getByText('Shared list', { exact: true })).toBeVisible()
  await page.goto('/lists')
  await expect(page.getByText('No lists on this device yet')).toBeVisible()
  // The list itself still exists for everyone.
  await page.goto(`/l/${list.public_code}`)
  await expect(page.getByRole('heading', { level: 1, name: 'Forget me' })).toBeVisible()
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
