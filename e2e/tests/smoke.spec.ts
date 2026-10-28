import { expect, test } from './fixtures'

test('the production app loads over HTTPS with its stylesheet and font', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveTitle('Share a list of links · listlinkedin')
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Collect links')
  const font = await page.evaluate(async () => {
    await document.fonts.ready
    return document.fonts.check('16px "Inter Variable"')
  })
  expect(font).toBe(true)
})
