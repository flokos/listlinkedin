// Link details fetched in the background (roadmap 7.3; the "tiles show fetched titles" step of
// scenario 1 in docs/v2/15-TEST-STRATEGY.md). The worker fetches a fixture site on the e2e
// network (e2e/fixture-site, served as http://fixture.test/), and the page shows its title,
// site name and icon without a reload. A page that can't be fetched says so in Details.
import { type Page } from '@playwright/test'

import { cardTitle, createAccountList, expect, signUpThroughApi, test, uniqueEmail } from './fixtures'

/** On phones the add form starts collapsed once a list has links. */
async function addLink(page: Page, url: string) {
  const toggle = page.getByRole('button', { name: 'Add a link' })
  if ((await toggle.getAttribute('aria-expanded')) === 'false') await toggle.click()
  await page.getByRole('textbox', { name: 'Link', exact: true }).fill(url)
  await page.getByRole('button', { name: 'Add link' }).click()
}

async function openDetails(page: Page, name: string) {
  await page.getByRole('button', { name: `More actions for ${name}` }).click()
  await page.getByRole('menuitem', { name: 'Details' }).click()
  return page.getByRole('dialog', { name: 'Link details' })
}

test("a new link shows its page's title, site and icon once fetched", async ({ page }) => {
  test.slow() // waits for the worker
  await signUpThroughApi(page, uniqueEmail('meta'))
  const { code } = await createAccountList(page, 'Fetched')
  await page.goto(`/l/${code}`)

  await addLink(page, 'http://fixture.test/')
  // First the host, while fetching; then the page's own details, without reloading.
  await expect(cardTitle(page, 'Fixture Tools')).toBeVisible({ timeout: 30_000 })
  const tile = page.locator('article', { has: cardTitle(page, 'Fixture Tools') })
  await expect(tile).toContainText('Fixture Site')
  await expect(tile).toHaveAttribute('aria-busy', 'false')
  await expect(tile.locator('img')).toHaveAttribute('src', /^\/media\/icons\/.+\.webp$/)

  const details = await openDetails(page, 'Fixture Tools')
  await expect(details).toContainText('Handy tools for end-to-end tests.')
  await details.getByRole('button', { name: 'Refresh details' }).click()
  await expect(details.getByRole('status')).toHaveText('Fetching the details again…')
  await details.getByRole('button', { name: 'Refresh details' }).click()
  await expect(details.getByRole('status')).toContainText('refreshed recently')
  await details.getByRole('button', { name: 'Close' }).click()

  // The fetched title is a suggestion in the edit form, never written into the link.
  await page.getByRole('button', { name: 'More actions for Fixture Tools' }).click()
  await page.getByRole('menuitem', { name: 'Edit' }).click()
  const edit = page.getByRole('dialog', { name: 'Edit link' })
  await expect(edit.getByRole('textbox', { name: 'Title (optional)' })).toHaveValue('')
  await edit.getByRole('button', { name: "Use the page's title, Fixture Tools" }).click()
  await expect(edit.getByRole('textbox', { name: 'Title (optional)' })).toHaveValue('Fixture Tools')
  await edit.getByRole('button', { name: 'Cancel' }).click()
})

test("a page that can't be fetched says so, and the link still works", async ({ page }) => {
  test.slow()
  await signUpThroughApi(page, uniqueEmail('meta-missing'))
  const { code } = await createAccountList(page, 'Missing')
  await page.goto(`/l/${code}`)

  await addLink(page, 'http://fixture.test/missing')
  await expect(cardTitle(page, 'fixture.test')).toBeVisible() // the host stands in
  const details = await openDetails(page, 'fixture.test')
  await expect(details).toContainText("Couldn't fetch details for this site", { timeout: 30_000 })
})
