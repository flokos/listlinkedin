// Sharing an account list with people (docs/v2/12-AUTHORIZATION.md): the owner adds an
// existing, verified account by email, changes what they may do, and members may leave.
import { cardTitle, expect, otherDevice, signUpVerified, test, uniqueEmail } from './fixtures'

test('share a private list with someone, let them edit, and they leave', async ({
  page,
  browser,
  baseURL,
}) => {
  test.slow() // two accounts on two devices
  const friend = await otherDevice(browser, baseURL)
  const friendEmail = uniqueEmail('friend')
  await signUpVerified(friend.page, friendEmail, 'Friend')
  await signUpVerified(page, uniqueEmail('owner'), 'Owner')

  await page.goto('/')
  await page.getByRole('textbox', { name: 'List name' }).fill('Team reading')
  await page.getByRole('button', { name: 'Create list' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Team reading' })).toBeVisible()
  const listUrl = page.url()

  // Private: the friend can't open it yet.
  await friend.page.goto(listUrl)
  await expect(friend.page.getByRole('heading', { level: 1, name: "This list doesn't exist" })).toBeVisible()

  await page.getByRole('button', { name: 'Share', exact: true }).click()
  const share = page.getByRole('dialog', { name: 'Share this list' })
  await share.getByRole('textbox', { name: 'Email address' }).fill(friendEmail)
  await share.getByRole('button', { name: 'Add', exact: true }).click()
  // Assert lasting state, not the toast: on a slow runner a toast can be gone before the check.
  await expect(share.getByRole('button', { name: 'Remove Friend' })).toBeVisible()

  // A viewer sees the list in My lists and can open it, but not change it.
  await friend.page.goto('/lists')
  await friend.page.getByRole('region', { name: 'Your lists' }).getByRole('link', { name: 'Team reading' }).click()
  await expect(friend.page.getByRole('heading', { level: 1, name: 'Team reading' })).toBeVisible()
  await expect(friend.page.getByRole('textbox', { name: 'Link', exact: true })).toBeHidden()

  // The owner lets them edit.
  // Vuetify's select: the named combobox is an inner input; open it through its field.
  const permission = page.getByRole('combobox', { name: 'Permission for Friend' })
  const permissionField = share.locator('.v-field', { has: permission })
  await permissionField.click()
  await page.getByRole('option', { name: 'Can edit' }).click()
  await expect(permissionField).toContainText('Can edit') // bound to the server's answer

  await friend.page.reload()
  await friend.page.getByRole('textbox', { name: 'Link', exact: true }).fill('https://example.com/shared')
  await friend.page.getByRole('button', { name: 'Add link' }).click()
  await expect(cardTitle(friend.page, 'example.com')).toBeVisible() // untitled: named by its host

  // The friend leaves; the private list is closed to them again.
  await friend.page.getByRole('button', { name: 'List options' }).click()
  await friend.page.getByRole('menuitem', { name: 'Leave list' }).click()
  await friend.page.getByRole('dialog', { name: 'Leave this list?' }).getByRole('button', { name: 'Leave list' }).click()
  await expect(friend.page.getByRole('heading', { level: 1, name: 'My lists' })).toBeVisible()
  await expect(friend.page.getByRole('link', { name: 'Team reading' })).toBeHidden()
  await friend.page.goto(listUrl)
  await expect(friend.page.getByRole('heading', { level: 1, name: "This list doesn't exist" })).toBeVisible()
  await friend.context.close()
})

test('adding an address without a verified account explains what is needed', async ({ page }) => {
  await signUpVerified(page, uniqueEmail('owner'), 'Owner')
  await page.goto('/')
  await page.getByRole('textbox', { name: 'List name' }).fill('Solo list')
  await page.getByRole('button', { name: 'Create list' }).click()
  await page.getByRole('button', { name: 'Share', exact: true }).click()
  const share = page.getByRole('dialog', { name: 'Share this list' })
  await share.getByRole('textbox', { name: 'Email address' }).fill(uniqueEmail('nobody'))
  await share.getByRole('button', { name: 'Add', exact: true }).click()
  await expect(share.getByText(/They need an account with a verified email address/)).toBeVisible()
  await expect(share.getByText('Nobody else has access yet.')).toBeVisible()
})

test('signed out, a private list suggests signing in', async ({ page }) => {
  await page.goto('/l/NoSuchList000000')
  await expect(page.getByText('If someone shared it with you, sign in to open it.')).toBeVisible()
  await page.getByRole('main').getByRole('link', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/signin\?next=/)
})
