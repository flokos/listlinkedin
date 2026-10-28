import { cardTitle, expect, openAsOwner, test } from './fixtures'

test('a full list (100 links) blocks adding until a link is deleted', async ({ page, api }) => {
  test.slow()
  const list = await api.createList('Full list')
  for (let i = 1; i <= 100; i++) await api.addLink(list, `https://example.com/item/${i}`, `Item ${i}`)
  await openAsOwner(page, list)

  await expect(page.getByText('100 / 100')).toBeVisible()
  await expect(page.getByText('This list has reached its limit of 100 links.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Add link' })).toBeDisabled()

  await expect(cardTitle(page, 'Item 100')).toBeVisible()
  await page.getByRole('button', { name: 'More actions for Item 100' }).click()
  await page.getByRole('menuitem', { name: 'Delete' }).click()
  await page.getByRole('button', { name: 'Delete link' }).click()
  await expect(page.getByText('99 / 100')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Add link' })).toBeEnabled()
})
