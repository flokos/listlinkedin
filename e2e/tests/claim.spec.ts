// V1 lists ("legacy" lists, managed by their edit link) move into an account: one from its
// page, or all at once from My lists. The edit link stops working afterwards.
import { editLinkFor, expect, openAsOwner, signUpThroughApi, test, uniqueEmail } from './fixtures'

test('add a legacy list to your account from its page', async ({ page, api, browser, baseURL }) => {
  const list = await api.createList('Old team links')
  await api.addLink(list, 'https://example.com/old', 'Old link')
  await openAsOwner(page, list)
  await signUpThroughApi(page, uniqueEmail('claim'))
  await page.reload()

  await page.getByRole('button', { name: 'List options' }).click()
  await page.getByRole('menuitem', { name: 'Add to my account' }).click()
  await expect(page.getByText('Added to your account. Its edit link no longer works.')).toBeVisible()

  // Its 30-day expiry stays unless the owner explicitly removes it.
  const keep = page.getByRole('dialog', { name: 'Keep this list permanently?' })
  await expect(keep).toBeVisible()
  await keep.getByRole('button', { name: 'Keep permanently' }).click()
  await expect(page.getByText('This list no longer expires')).toBeVisible()
  await expect(page.getByText(/Expires in/)).toBeHidden()

  await page.goto('/lists')
  const yours = page.getByRole('region', { name: 'Your lists' })
  await expect(yours.getByRole('link', { name: 'Old team links' })).toBeVisible()

  // The old edit link is dead everywhere, including on another device.
  const other = await browser.newContext({ baseURL, ignoreHTTPSErrors: true })
  const otherPage = await other.newPage()
  await otherPage.goto(editLinkFor(list))
  await expect(otherPage.getByRole('heading', { level: 1 })).not.toHaveText('Old team links')
  await other.close()
})

test('add every list saved on this device from My lists', async ({ page, api }) => {
  const first = await api.createList('Device list one')
  const second = await api.createList('Device list two')
  await openAsOwner(page, first)
  await openAsOwner(page, second)
  await signUpThroughApi(page, uniqueEmail('bulk'))

  await page.goto('/lists')
  await page.getByRole('button', { name: 'Add all to my account' }).click()
  await expect(page.getByText('Added 2 lists to your account')).toBeVisible()
  const yours = page.getByRole('region', { name: 'Your lists' })
  await expect(yours.getByRole('link', { name: 'Device list one' })).toBeVisible()
  await expect(yours.getByRole('link', { name: 'Device list two' })).toBeVisible()
})
