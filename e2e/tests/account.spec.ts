// Deleting an account (docs/v2/09-API-DESIGN.md): type-to-confirm, the owned lists go with it,
// and the browser is signed out.
import { expect, signUpThroughApi, test, uniqueEmail } from './fixtures'

test('delete an account and the lists it owns', async ({ page }) => {
  const email = uniqueEmail('delete')
  await signUpThroughApi(page, email)
  await page.goto('/')
  await page.getByRole('textbox', { name: 'List name' }).fill('Short-lived list')
  await page.getByRole('button', { name: 'Create list' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Short-lived list' })).toBeVisible()
  const listUrl = page.url()

  await page.goto('/account')
  await page.getByRole('button', { name: 'Delete account…' }).click()
  const dialog = page.getByRole('dialog', { name: 'Delete your account?' })
  await expect(dialog.getByText(/The list you own, with all its links/)).toBeVisible()
  const confirm = dialog.getByRole('button', { name: 'Delete account' })
  await expect(confirm).toBeDisabled()
  await dialog.getByRole('textbox').fill(email)
  await confirm.click()

  await expect(page.getByRole('heading', { level: 1, name: /Collect links/ })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Create a free account' })).toBeVisible() // signed out
  await page.goto(listUrl)
  await expect(page.getByRole('heading', { level: 1, name: "This list doesn't exist" })).toBeVisible()
})
