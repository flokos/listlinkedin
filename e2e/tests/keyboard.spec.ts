import { cardTitle, expect, signUpThroughApi, test, uniqueEmail } from './fixtures'

test.skip(({ isMobile }) => isMobile, 'keyboard navigation is a desktop concern')

async function tabUntil(page: import('@playwright/test').Page, check: () => Promise<boolean>, max = 25) {
  for (let i = 0; i < max; i++) {
    if (await check()) return
    await page.keyboard.press('Tab')
  }
  throw new Error('target never received focus')
}

test('create a list and add a link with the keyboard only', async ({ page }) => {
  await signUpThroughApi(page, uniqueEmail('keyboard'))
  await page.goto('/')
  const name = page.getByRole('textbox', { name: 'List name' })
  await tabUntil(page, () => name.evaluate((el) => el === document.activeElement))
  await page.keyboard.type('Keyboard only')
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { level: 1, name: 'Keyboard only' })).toBeVisible()

  const url = page.getByRole('textbox', { name: 'Link', exact: true })
  await tabUntil(page, () => url.evaluate((el) => el === document.activeElement), 40)
  await page.keyboard.type('example.org/keyboard')
  await page.keyboard.press('Enter')
  await expect(cardTitle(page, 'example.org')).toBeVisible() // untitled: named by its host
  await expect(url).toBeFocused() // ready for the next link
})
