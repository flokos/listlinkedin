// Explore (roadmap 8.2; scenario 5 in docs/v2/15-TEST-STRATEGY.md): the owner tags a public
// list in the UI, and a visitor finds it by a partial word and by its tag. An unlisted list
// with the same words never shows. Every test shares one database, so the words are unique.
import { apiAs, createAccountList, expect, otherDevice, signUpVerified, test, uniqueEmail } from './fixtures'

/** A word nothing else in the database contains. */
const uniqueWord = () => `zq${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`

test('a public list is found by words and tags; an unlisted one never is', async ({ page, browser, baseURL }) => {
  test.slow() // two devices
  const word = uniqueWord()
  await signUpVerified(page, uniqueEmail('explore'), 'Explorer')
  const shown = await createAccountList(page, `${word}cheatsheets`)
  await apiAs(page, 'PATCH', `/api/v2/lists/${shown.code}/`, { visibility: 'public', description: 'Handy commands' }, 200)
  const hidden = await createAccountList(page, `${word} unlisted`)
  await apiAs(page, 'PATCH', `/api/v2/lists/${hidden.code}/`, { visibility: 'unlisted' }, 200)

  // The owner tags the public list; the tag is normalized and shown under the title.
  await page.goto(`/l/${shown.code}`)
  await page.getByRole('button', { name: 'List options' }).click()
  await page.getByRole('menuitem', { name: 'Tags…' }).click()
  const dialog = page.getByRole('dialog', { name: 'Tags' })
  await dialog.getByRole('combobox', { name: 'Tags (optional)' }).fill(`${word} Tools`)
  await page.keyboard.press('Enter')
  await dialog.getByRole('button', { name: 'Save tags' }).click()
  await expect(dialog).toBeHidden()
  const tag = `${word}-tools`
  await expect(page.getByRole('link', { name: `${tag}: explore lists with this tag` })).toBeVisible()

  // A visitor, signed out, searches by the start of the name.
  const visitor = await otherDevice(browser, baseURL)
  await visitor.page.goto('/explore')
  await expect(visitor.page.getByRole('heading', { level: 1, name: 'Explore' })).toBeVisible()
  await visitor.page.getByRole('searchbox', { name: 'Search public lists' }).fill(word.slice(0, -1))
  await visitor.page.keyboard.press('Enter')
  const results = visitor.page.getByRole('list', { name: 'Public lists' })
  await expect(results.getByRole('link')).toHaveText([`${word}cheatsheets`])
  await expect(results).toContainText('By Explorer · 0 links')

  // Its tag narrows the search; the address keeps it, so reloading shows the same.
  await visitor.page.getByRole('searchbox', { name: 'Search public lists' }).fill('')
  await visitor.page.keyboard.press('Enter')
  await visitor.page.goto(`/explore?tags=${tag}`)
  await expect(results.getByRole('link')).toHaveText([`${word}cheatsheets`])
  await expect(visitor.page.getByRole('button', { name: tag, exact: true })).toHaveAttribute('aria-pressed', 'true')
  await visitor.page.reload()
  await expect(results.getByRole('link')).toHaveText([`${word}cheatsheets`])

  // Words that match only the unlisted list find nothing, and the search can be cleared.
  await visitor.page.goto(`/explore?q=${word}%20unlisted`)
  await expect(visitor.page.getByRole('heading', { name: 'No lists match' })).toBeVisible()
  await visitor.page.getByRole('button', { name: 'Clear search', exact: true }).click()
  await expect(visitor.page).toHaveURL(/\/explore$/)

  // Opening a result leads to the list.
  await visitor.page.goto(`/explore?q=${word}`)
  await results.getByRole('link', { name: `${word}cheatsheets` }).click()
  await expect(visitor.page.getByRole('heading', { level: 1, name: `${word}cheatsheets` })).toBeVisible()
  await visitor.context.close()
})

test('public groups have their own tab', async ({ page }) => {
  const word = uniqueWord()
  await signUpVerified(page, uniqueEmail('explore-group'), 'Group maker')
  const group = await apiAs(page, 'POST', '/api/v2/groups/', { title: `${word} portal`, tags: ['platform'] })
  await apiAs(page, 'PATCH', `/api/v2/groups/${group.code}/`, { visibility: 'public' }, 200)

  await page.goto(`/explore?q=${word}`)
  await expect(page.getByRole('heading', { name: 'No lists match' })).toBeVisible()
  await page.getByRole('tab', { name: 'Groups' }).click()
  await expect(page).toHaveURL(new RegExp(`in=groups`))
  const results = page.getByRole('list', { name: 'Public groups' })
  await expect(results.getByRole('link')).toHaveText([`${word} portal`])
  await expect(results).toContainText('0 lists')
})
