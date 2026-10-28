import { cardTitle, expect, openAsOwner, test } from './fixtures'

const noHorizontalOverflow = async (page: import('@playwright/test').Page) =>
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth),
  ).toBeLessThanOrEqual(0)

test('long, emoji and right-to-left content never breaks the layout', async ({ page, api }) => {
  const longTitle = `${'Supercalifragilistic '.repeat(12)}end`.slice(0, 255)
  const list = await api.createList(longTitle)
  await api.addLink(list, `https://example.com/${'very-long-path-segment/'.repeat(80)}`.slice(0, 2000), '🎉 Party ideas 🎈')
  await api.addLink(list, 'https://example.org/rtl', 'قائمة الروابط المفيدة للفريق')
  await api.addLink(list, `https://example.net/${'x'.repeat(300)}`)
  await openAsOwner(page, list)

  await expect(page.getByRole('heading', { level: 1 })).toContainText('Supercalifragilistic')
  await expect(cardTitle(page, '🎉 Party ideas 🎈')).toBeVisible()
  await expect(cardTitle(page, 'قائمة الروابط المفيدة للفريق')).toBeVisible()
  await noHorizontalOverflow(page)

  await page.goto('/lists')
  await expect(page.locator('main').getByRole('link', { name: /Supercalifragilistic/ })).toBeVisible()
  await noHorizontalOverflow(page)
})
