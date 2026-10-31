// A list's settings page (roadmap 8.3): each section shows only to whoever may change it, the
// description is versioned and refused when someone else changed the list meanwhile, and the
// header shows what was saved.
import { apiAs, createAccountList, expect, otherDevice, signUpThroughApi, test, uniqueEmail } from './fixtures'

// A 1×1 PNG: the server re-encodes whatever it gets.
const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAEBgIApD5fRAAAAABJRU5ErkJggg==',
  'base64',
)

test('the owner changes the description, image and expiry, and the list shows them', async ({ page }) => {
  await signUpThroughApi(page, uniqueEmail('settings'))
  const { code } = await createAccountList(page, 'Team tools')
  await page.goto(`/l/${code}`)
  await page.getByRole('button', { name: 'List options' }).click()
  await page.getByRole('menuitem', { name: 'Settings' }).click()
  await expect(page).toHaveURL(new RegExp(`/l/${code}/settings$`))
  await expect(page.getByRole('heading', { level: 2 })).toHaveText([
    'Name and description',
    'Image',
    'Tags',
    'Sharing',
    'Expiry',
    'Delete this list',
  ])

  await page.getByRole('textbox', { name: 'Description (optional)' }).fill('What the team uses every day')
  await page.getByRole('button', { name: 'Save name and description' }).click()
  await expect(page.getByText('Name and description saved')).toBeVisible()
  await expect(page.getByRole('textbox', { name: 'Description (optional)' })).toHaveValue(
    'What the team uses every day',
  )

  await page.locator('input[type=file]').setInputFiles({ name: 'team.png', mimeType: 'image/png', buffer: PNG })
  await expect(page.getByText('Image updated')).toBeVisible()

  await page.getByRole('radio', { name: 'Delete it automatically on a date' }).check()
  await page.getByLabel('Delete at the end of').fill('2099-12-31')
  await page.getByRole('button', { name: 'Save expiry' }).click()
  await expect(page.getByText('Expiry date saved')).toBeVisible()

  await page.getByRole('link', { name: 'Team tools' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Team tools' })).toBeVisible()
  await expect(page.getByText('What the team uses every day')).toBeVisible()
  await expect(page.locator('img.ll-list-image')).toHaveAttribute('src', /^\/media\/.+\.webp$/)
  await expect(page.getByText(/Expires in/)).toBeVisible()
})

test('a description changed elsewhere meanwhile is refused, then shown', async ({ page }) => {
  await signUpThroughApi(page, uniqueEmail('settings-stale'))
  const { code } = await createAccountList(page, 'Shared notes')
  await page.goto(`/l/${code}/settings`)
  const field = page.getByRole('textbox', { name: 'Description (optional)' })
  await expect(field).toHaveValue('')

  // Another tab saves first.
  await apiAs(page, 'PATCH', `/api/v2/lists/${code}/`, { description: 'From the other tab' }, 200)
  await field.fill('From this tab')
  await page.getByRole('button', { name: 'Save name and description' }).click()
  await expect(page.getByText('Someone changed this list while you were editing')).toBeVisible()
  await expect(field).toHaveValue('From the other tab')
})

test("visitors can't change anything", async ({ page, browser, baseURL }) => {
  await signUpThroughApi(page, uniqueEmail('settings-owner'))
  const { code } = await createAccountList(page, 'Open list')
  await apiAs(page, 'PATCH', `/api/v2/lists/${code}/`, { visibility: 'unlisted' }, 200)

  const visitor = await otherDevice(browser, baseURL)
  await visitor.page.goto(`/l/${code}`)
  await expect(visitor.page.getByRole('heading', { level: 1, name: 'Open list' })).toBeVisible()
  await visitor.page.getByRole('button', { name: 'List options' }).click()
  await expect(visitor.page.getByRole('menuitem')).toHaveText(['Report…']) // no Settings
  await visitor.page.keyboard.press('Escape')
  await visitor.page.goto(`/l/${code}/settings`)
  await expect(visitor.page.getByRole('heading', { name: "You can't change this list's settings" })).toBeVisible()
  await visitor.context.close()
})
