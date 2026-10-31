// History (roadmap 3.4, e2e scenario 6 in docs/v2/15-TEST-STRATEGY.md): every change is a
// version; restoring an old one adds a new version, and its links come back with the same
// short URLs.
import { cardTitle, cardTitles, expect, openAsOwner, test } from './fixtures'

test('restore an earlier version: the links come back with the same short URLs', async ({ page, api, request }) => {
  const list = await api.createList('Reading')
  await api.addLink(list, 'https://alpha.example/', 'Alpha')
  const bravo = await api.addLink(list, 'https://bravo.example/', 'Bravo') // version 3
  await openAsOwner(page, list)

  await page.getByRole('button', { name: 'More actions for Bravo' }).click()
  await page.getByRole('menuitem', { name: 'Delete' }).click()
  await page.getByRole('button', { name: 'Delete link' }).click()
  await expect(cardTitle(page, 'Bravo')).toBeHidden()
  expect((await request.get(bravo.short_url, { maxRedirects: 0 })).status()).toBe(404)

  await page.getByRole('button', { name: 'List options' }).click()
  await page.getByRole('menuitem', { name: 'History' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'History' })).toBeVisible()
  await expect(page.getByRole('heading', { level: 2, name: /Version 4/ })).toBeVisible() // current
  await expect(page.getByText('Bravo · Removed')).toBeVisible()

  await page.getByRole('link', { name: /^Version 3/ }).click()
  await expect(page.getByRole('heading', { level: 2, name: 'Version 3' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Links in this version (2)' })).toBeVisible()
  await page.getByRole('button', { name: 'Restore this version' }).click()
  const confirm = page.getByRole('dialog', { name: 'Restore version 3?' })
  await expect(confirm.getByText(/Creates version 5 with this content/)).toBeVisible()
  await confirm.getByRole('button', { name: 'Restore this version' }).click()

  await expect(page.getByRole('heading', { level: 2, name: /Version 5/ })).toBeVisible()
  await expect(page.getByRole('link', { name: /^Version 5.*Restored version 3/ })).toBeVisible()
  expect((await request.get(bravo.short_url, { maxRedirects: 0 })).status()).toBe(302)

  await page.locator('#main').getByRole('link', { name: 'Reading' }).click()
  await expect(cardTitles(page)).toHaveText([/Alpha/, /Bravo/])
  await expect(cardTitle(page, 'Bravo')).toHaveAttribute('href', bravo.short_url)
})

test('people who can only view a list never see its history', async ({ page, api }) => {
  const list = await api.createList('Visitors')
  await page.goto(`/l/${list.public_code}/history`)
  await expect(
    page.getByRole('heading', { level: 1, name: "Only the list's editors can see its history" }),
  ).toBeVisible()
})
