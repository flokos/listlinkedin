// My lists (/lists): the lists in your account, owned or shared with you. (Until v2.1.0 it
// also held lists saved on this device with an edit link, and their backup file.)
import { apiAs, createAccountList, expect, signUpThroughApi, test, uniqueEmail } from './fixtures'

test('signed out, My lists asks you to sign in', async ({ page }) => {
  await page.goto('/lists')
  await expect(page.getByRole('heading', { level: 1, name: 'My lists' })).toBeVisible()
  await expect(page.getByText('Sign in to see your lists')).toBeVisible()
  await expect(page.getByRole('main').getByRole('link', { name: 'Sign in' })).toBeVisible()
})

test('My lists shows your lists with their role, visibility and size', async ({ page }) => {
  await signUpThroughApi(page, uniqueEmail('mylists'))
  await page.goto('/lists')
  await expect(page.getByRole('heading', { name: 'No lists yet' })).toBeVisible()

  const list = await createAccountList(page, 'Reading list')
  await apiAs(page, 'POST', `/api/v2/lists/${list.code}/links/`, { destination_url: 'https://example.com/' })
  await page.goto('/lists')
  const yours = page.getByRole('region', { name: 'Your lists' })
  await expect(yours.getByRole('link', { name: 'Reading list' })).toBeVisible()
  await expect(yours.getByText('Owner')).toBeVisible()
  await expect(yours.getByText('Only people you add')).toBeVisible()
  await expect(yours.getByText('1 link')).toBeVisible()
  await yours.getByRole('link', { name: 'Reading list' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Reading list' })).toBeVisible()
})
