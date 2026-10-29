// Links as tiles (roadmap 2.4, docs/v2/11-UI-UX-MIGRATION.md#list-page): descriptions, an
// uploaded icon, Details, and the grid/list choice remembered on this device.
import { cardTitle, expect, signUpVerified, test, uniqueEmail } from './fixtures'

// A 1×1 PNG. The server re-encodes every upload to WebP.
const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
  'base64',
)

test('describe a link, give it an icon, read its details and switch layouts', async ({ page }) => {
  await signUpVerified(page, uniqueEmail('tiles'), 'Tiler')
  await page.goto('/')
  await page.getByRole('textbox', { name: 'List name' }).fill('Reading')
  await page.getByRole('button', { name: 'Create list' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Reading' })).toBeVisible()

  await page.getByRole('textbox', { name: 'Link', exact: true }).fill('https://example.com/essay')
  await page.getByRole('textbox', { name: 'Title (optional)' }).fill('An essay')
  await page.getByRole('textbox', { name: 'Description (optional)' }).fill('Long, but worth it.')
  await page.getByRole('button', { name: 'Add link' }).click()

  // Grid is the default: the tile shows the name, the site and the description.
  const tile = page.getByRole('article').filter({ has: cardTitle(page, 'An essay') })
  await expect(tile).toContainText('example.com')
  await expect(tile).toContainText('Long, but worth it.')
  await expect(tile.locator('img')).toHaveCount(0) // no icon yet: the letter avatar

  // An uploaded icon, served by nginx from /media/.
  await tile.getByRole('button', { name: 'More actions for An essay' }).click()
  await page.getByRole('menuitem', { name: 'Edit' }).click()
  const dialog = page.getByRole('dialog', { name: 'Edit link' })
  await dialog.getByLabel('Choose icon').setInputFiles({ name: 'icon.png', mimeType: 'image/png', buffer: PNG })
  await expect(dialog.getByRole('button', { name: 'Remove' })).toBeVisible()
  await dialog.getByRole('button', { name: 'Cancel' }).click()
  const icon = tile.locator('img')
  await expect(icon).toHaveAttribute('src', /^\/media\/icons\/.+\.webp$/)
  await expect.poll(() => icon.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0)

  // Details: everything the tile clamps, and the short link.
  await tile.getByRole('button', { name: 'More actions for An essay' }).click()
  await page.getByRole('menuitem', { name: 'Details' }).click()
  const details = page.getByRole('dialog', { name: 'Link details' })
  await expect(details).toContainText('Long, but worth it.')
  await expect(details.getByRole('textbox', { name: 'Short link' })).toHaveValue(/\/r\//)
  await details.getByRole('button', { name: 'Close' }).click()

  // List view is remembered on this device.
  await page.getByRole('button', { name: 'List view' }).click()
  await page.reload()
  await expect(page.getByRole('button', { name: 'Copy short link for An essay' })).toBeVisible()
  await expect(page.getByText('example.com/essay', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Grid view' }).click()
  await expect(page.getByRole('button', { name: 'Copy short link for An essay' })).toBeHidden()
})
