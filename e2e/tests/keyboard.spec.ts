import { expect, test } from './fixtures'

test.skip(({ isMobile }) => isMobile, 'keyboard navigation is a desktop concern')

async function tabUntil(page: import('@playwright/test').Page, check: () => Promise<boolean>, max = 25) {
  for (let i = 0; i < max; i++) {
    if (await check()) return
    await page.keyboard.press('Tab')
  }
  throw new Error('target never received focus')
}

test('create a list and add a link with the keyboard only', async ({ page }) => {
  await page.goto('/')
  const name = page.getByRole('textbox', { name: 'List name' })
  await tabUntil(page, () => name.evaluate((el) => el === document.activeElement))
  await page.keyboard.type('Keyboard only')
  await page.keyboard.press('Enter')

  const dialog = page.getByRole('dialog', { name: 'Your list is ready. Save your edit link' })
  await expect(dialog).toBeVisible()
  const ack = dialog.getByRole('checkbox', { name: /saved my edit link/ })
  await tabUntil(page, () => ack.evaluate((el) => el === document.activeElement))
  await page.keyboard.press('Space')
  const go = dialog.getByRole('button', { name: 'Go to my list' })
  await tabUntil(page, () => go.evaluate((el) => el === document.activeElement))
  await page.keyboard.press('Enter')
  await expect(dialog).toBeHidden()

  const url = page.getByRole('textbox', { name: 'Link', exact: true })
  await tabUntil(page, () => url.evaluate((el) => el === document.activeElement), 40)
  await page.keyboard.type('example.org/keyboard')
  await page.keyboard.press('Enter')
  await expect(page.getByText('example.org/keyboard', { exact: true })).toBeVisible()
  await expect(url).toBeFocused() // ready for the next link
})
