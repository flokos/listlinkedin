// Deleting an account (docs/v2/adr/ADR-016): type-to-confirm; the owned lists disappear and
// the browser is signed out at once; signing in within 30 days offers to restore everything.
import { expect, PASSWORD, signUpThroughApi, test, uniqueEmail } from './fixtures'

test('delete an account, then restore it by signing in again', async ({ page }) => {
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
  await expect(dialog.getByText(/sign in to restore your account/)).toBeVisible()
  const confirm = dialog.getByRole('button', { name: 'Delete account' })
  await expect(confirm).toBeDisabled()
  await dialog.getByRole('textbox').fill(email)
  await confirm.click()

  await expect(page.getByRole('heading', { level: 1, name: /Collect links/ })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Create a free account' })).toBeVisible() // signed out
  await page.goto(listUrl)
  await expect(page.getByRole('heading', { level: 1, name: "This list doesn't exist" })).toBeVisible()

  // Signing in again within the grace period leads to the restore page, and only there.
  await page.goto('/signin')
  await page.getByRole('textbox', { name: 'Email' }).fill(email)
  await page.getByLabel('Password', { exact: true }).fill(PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).last().click()
  const restoreHeading = page.getByRole('heading', { level: 1, name: 'Your account is being deleted' })
  await expect(restoreHeading).toBeVisible()
  await page.goto(listUrl)
  await expect(restoreHeading).toBeVisible()

  await page.getByRole('button', { name: 'Restore my account' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'My lists' })).toBeVisible()
  await page.goto(listUrl)
  await expect(page.getByRole('heading', { level: 1, name: 'Short-lived list' })).toBeVisible()
})
