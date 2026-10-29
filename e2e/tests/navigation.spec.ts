import { expect, test } from './fixtures'

test.describe('desktop menu', () => {
  test.skip(({ isMobile }) => isMobile, 'mobile uses the drawer')

  test('navigates without reloading, with titles, active state and focus on the heading', async ({ page }) => {
    await page.goto('/')
    await page.evaluate(() => ((window as unknown as { marker: string }).marker = 'same document'))
    const nav = page.getByRole('navigation', { name: 'Main' })

    for (const [link, heading, title] of [
      ['My lists', 'My lists', 'My lists · listlinkedin'],
      ['About', 'About & privacy', 'About & privacy · listlinkedin'],
      ['Home', /Collect links/, 'Share a list of links · listlinkedin'],
    ] as const) {
      await nav.getByRole('link', { name: link }).click()
      const h1 = page.getByRole('heading', { level: 1, name: heading })
      await expect(h1).toBeVisible()
      await expect(page).toHaveTitle(title)
      await expect(nav.getByRole('link', { name: link })).toHaveAttribute('aria-current', 'page')
      await expect(h1).toBeFocused()
    }
    await page.getByRole('navigation', { name: 'Footer' }).getByRole('link', { name: 'About' }).click()
    await expect(page.getByRole('heading', { level: 1, name: 'About & privacy' })).toBeVisible()
    expect(await page.evaluate(() => (window as unknown as { marker?: string }).marker)).toBe('same document')
  })

  test('the skip link is the first tab stop and jumps to the content', async ({ page }) => {
    await page.goto('/about')
    await page.keyboard.press('Tab')
    const skip = page.getByRole('link', { name: 'Skip to content' })
    await expect(skip).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page.locator('main')).toBeFocused()
  })
})

test.describe('mobile menu', () => {
  test.skip(({ isMobile }) => !isMobile, 'desktop uses the app bar')

  test('the drawer opens with focus inside, closes on Escape, and navigates', async ({ page }) => {
    await page.goto('/about')
    const opener = page.getByRole('button', { name: 'Open menu' })
    await opener.click()
    const drawer = page.getByRole('dialog', { name: 'Menu' })
    await expect(drawer).toBeVisible()
    await expect(drawer.getByRole('link', { name: 'Home' })).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(drawer).toBeHidden()
    await expect(opener).toBeFocused()

    await opener.click()
    await drawer.getByRole('link', { name: 'My lists' }).click()
    await expect(page.getByRole('heading', { level: 1, name: 'My lists' })).toBeVisible()
    await expect(drawer).toBeHidden()
    // The compact "New list" button is reachable on small screens.
    await page.getByRole('banner').getByRole('link', { name: 'New list' }).click()
    await expect(page.getByRole('textbox', { name: 'List name' })).toBeVisible()
  })
})

test('every route works as a deep link (hard reload)', async ({ page, api }) => {
  const list = await api.createList('Deep link')
  for (const [path, heading] of [
    ['/', /Collect links/],
    ['/lists', 'My lists'],
    ['/about', 'About & privacy'],
    [`/l/${list.public_code}`, 'Deep link'],
    ['/no/such/page', 'Page not found'],
  ] as const) {
    await page.goto(path)
    await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible()
  }
  // The style guide is development-only.
  await page.goto('/design')
  await expect(page.getByRole('heading', { level: 1, name: 'Page not found' })).toBeVisible()
})
