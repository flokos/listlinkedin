// Automated WCAG 2.2 A/AA checks with axe, in light and dark mode. Complements (does not
// replace) the manual screen-reader checks in docs/qa-checklist.md.
import {
  apiAs,
  createAccountList,
  expect,
  expectNoA11yViolations,
  openAsOwner,
  signUpThroughApi,
  signUpVerified,
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

    test("an account list's share dialog with its People section", async ({ page }) => {
      await signUpVerified(page, uniqueEmail('a11y-owner'), 'Owner')
      await page.goto('/')
      await page.getByRole('textbox', { name: 'List name' }).fill('Shared with people')
      await page.getByRole('button', { name: 'Create list' }).click()
      await page.getByRole('button', { name: 'Share', exact: true }).click()
      await expect(page.getByRole('heading', { name: 'People', exact: true })).toBeVisible()
      await expect(page.getByText('Nobody else has access yet.')).toBeVisible()
      await expectNoA11yViolations(page)
    })

    test('the groups page and a group workspace with its sidebar and dialogs', async ({ page }) => {
      await signUpThroughApi(page, uniqueEmail('a11y-group'))
      const group = await apiAs(page, 'POST', '/api/v2/groups/', { title: 'Accessible group' })
      for (const title of ['First list', 'Second list']) {
        const list = await createAccountList(page, title)
        await apiAs(page, 'POST', `/api/v2/groups/${group.code}/lists/`, { list: list.code })
      }
      await page.goto('/groups')
      await expect(page.getByRole('link', { name: 'Accessible group' })).toBeVisible()
      await expectNoA11yViolations(page)

      await page.goto(new URL(group.url).pathname)
      await expect(page.getByRole('heading', { level: 1, name: 'First list' })).toBeVisible()
      await expectNoA11yViolations(page)

      await page.getByRole('button', { name: 'More actions for the group Accessible group' }).click()
      await page.getByRole('menuitem', { name: 'Reorder lists' }).click()
      await expect(page.getByRole('button', { name: 'Move Second list up' })).toBeVisible()
      await expectNoA11yViolations(page)
      await page.getByRole('button', { name: 'Done' }).click()

      await page.getByRole('button', { name: 'More actions for the group Accessible group' }).click()
      await page.getByRole('menuitem', { name: 'Add lists' }).click()
      await expect(page.getByRole('dialog', { name: 'Add lists to the group' }).getByText('In this group')).toHaveCount(2)
      await expectNoA11yViolations(page)
    })

        test("a list's history with a version's changes and the restore dialog", async ({ page, api }) => {
      const list = await api.createList('Accessible history')
      await api.addLink(list, 'https://example.com/a', 'First')
      await api.addLink(list, 'https://example.com/b', 'Second')
      await openAsOwner(page, list)
      await page.goto(`/l/${list.public_code}/history?v=2`)
      await expect(page.getByRole('heading', { level: 2, name: 'Version 2' })).toBeVisible()
      await expectNoA11yViolations(page)
      await page.getByRole('button', { name: 'Restore this version' }).click()
      await expect(page.getByRole('dialog', { name: 'Restore version 2?' })).toBeVisible()
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
