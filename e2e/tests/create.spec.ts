// Creating lists needs an account (docs/v2/adr/ADR-011). New lists are private, permanent,
// and editable right away through the account: no edit link to save.
import { expect, signUpThroughApi, test, uniqueEmail } from './fixtures'

test('signed out, Home invites you to create an account instead of a list', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('link', { name: 'Create a free account' })).toBeVisible()
  await expect(page.getByRole('textbox', { name: 'List name' })).toBeHidden()
})

test('a signed-in user creates a private list and edits it at once', async ({ page }) => {
  await signUpThroughApi(page, uniqueEmail('create'))
  await page.goto('/')
  await page.getByRole('textbox', { name: 'List name' }).fill('Friday team bonding')
  await page.getByRole('button', { name: 'Create list' }).click()

  await expect(page.getByRole('heading', { level: 1, name: 'Friday team bonding' })).toBeVisible()
  await expect(page).toHaveURL(/\/l\/[\w-]+\/friday-team-bonding$/)
  await expect(page.getByText('Your list', { exact: true })).toBeVisible()
  await expect(page.getByText('Only people you add')).toBeVisible()
  await expect(page.getByText('Add your first link')).toBeVisible()

  await page.getByRole('textbox', { name: 'Link', exact: true }).fill('https://example.com/a')
  await page.getByRole('button', { name: 'Add link' }).click()
  await expect(page.getByText('Link added')).toBeVisible()

  await page.goto('/lists')
  await expect(page.getByRole('heading', { level: 1, name: 'My lists' })).toBeVisible()
  const yours = page.getByRole('region', { name: 'Your lists' })
  await expect(yours.getByRole('link', { name: 'Friday team bonding' })).toBeVisible()
  await expect(yours.getByText('Owner')).toBeVisible()
})

test('an empty name is rejected without a request', async ({ page }) => {
  await signUpThroughApi(page, uniqueEmail('empty'))
  await page.goto('/')
  await page.getByRole('button', { name: 'Create list' }).click()
  await expect(page.getByText('Give your list a name.')).toBeVisible()
})
