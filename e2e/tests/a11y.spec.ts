// Automated WCAG 2.2 A/AA checks with axe, in light and dark mode. Complements (does not
// replace) the manual screen-reader checks in docs/qa-checklist.md.
import {
  expect,
  expectNoA11yViolations,
  openAsOwner,
  signUpThroughApi,
  test,
  uniqueEmail,
} from './fixtures'

for (const colorScheme of ['light', 'dark'] as const) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme })

    test('static pages', async ({ page }) => {
      for (const [path, heading] of [
        ['/', /Collect links/],
        ['/lists', 'My lists'],
        ['/about', 'About & privacy'],
        ['/no/such/page', 'Page not found'],
      ] as const) {
        await page.goto(path)
        await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible()
        await expectNoA11yViolations(page)
      }
    })

    test('sign-in, sign-up and password pages', async ({ page }) => {
      for (const [path, heading] of [
        ['/signin', 'Sign in'],
        ['/signup', 'Create your account'],
        ['/reset-password', 'Reset your password'],
      ] as const) {
        await page.goto(path)
        await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible()
        await expectNoA11yViolations(page)
      }
    })

    test('the account page and the account menu', async ({ page }) => {
      await signUpThroughApi(page, uniqueEmail('a11y'))
      await page.goto('/account')
      await expect(page.getByRole('heading', { level: 1, name: 'Your account' })).toBeVisible()
      await expectNoA11yViolations(page)

      await page.getByRole('button', { name: 'Account menu' }).click()
      await expect(page.getByRole('menuitem', { name: 'Sign out' })).toBeVisible()
      await expectNoA11yViolations(page)
    })

    test('a list as visitor and owner, with its dialogs', async ({ page, api }) => {
      const list = await api.createList('Accessible list')
      await api.addLink(list, 'https://example.com/a', 'A titled link')
      await api.addLink(list, 'https://example.org/untitled')

      await page.goto(`/l/${list.public_code}`)
      await expect(page.getByRole('heading', { level: 1, name: 'Accessible list' })).toBeVisible()
      await expectNoA11yViolations(page)

      await page.getByRole('button', { name: 'Share', exact: true }).click()
      await expect(page.getByRole('img', { name: /QR code/ })).toBeVisible()
      await expectNoA11yViolations(page)
      await page.keyboard.press('Escape')

      await openAsOwner(page, list)
      await expectNoA11yViolations(page)

      await page.getByRole('button', { name: 'List options' }).click()
      await page.getByRole('menuitem', { name: 'Show edit link' }).click()
      await expect(page.getByRole('dialog', { name: 'Your edit link' })).toBeVisible()
      await expectNoA11yViolations(page)
      await page.getByRole('button', { name: 'Done' }).click()

      await page.getByRole('button', { name: 'List options' }).click()
      await page.getByRole('menuitem', { name: 'Delete list' }).click()
      await expect(page.getByRole('dialog', { name: 'Delete this list?' })).toBeVisible()
      await expectNoA11yViolations(page)
    })
  })
}
