// Automated WCAG 2.2 A/AA checks with axe, in light and dark mode. Complements (does not
// replace) the manual screen-reader checks in docs/qa-checklist.md.
import {
  apiAs,
  createAccountList,
  csrfOf,
  emailTo,
  expect,
  expectNoA11yViolations,
  openAsOwner,
  signUpThroughApi,
  signUpVerified,
  linkIn,
  PASSWORD,
  test,
  uniqueEmail,
} from './fixtures'

// Each test runs several axe scans, which take seconds each on a busy machine.
test.describe.configure({ timeout: 120_000 })

for (const colorScheme of ['light', 'dark'] as const) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme })

    test('static pages', async ({ page }) => {
      for (const [path, heading] of [
        ['/', /Collect links/],
        ['/lists', 'My lists'],
        ['/about', 'About & privacy'],
        ['/explore', 'Explore'],
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

    test("an account list's share dialog with its People section, and its settings page", async ({ page }) => {
      await signUpVerified(page, uniqueEmail('a11y-owner'), 'Owner')
      await page.goto('/')
      await page.getByRole('textbox', { name: 'List name' }).fill('Shared with people')
      await page.getByRole('button', { name: 'Create list' }).click()
      await page.getByRole('button', { name: 'Share', exact: true }).click()
      await expect(page.getByRole('heading', { name: 'People', exact: true })).toBeVisible()
      await expect(page.getByText('Nobody else has access yet.')).toBeVisible()
      await expectNoA11yViolations(page)
      await page.getByRole('dialog', { name: 'Share this list' }).getByRole('button', { name: 'Close' }).click()

      await page.getByRole('button', { name: 'List options' }).click()
      await page.getByRole('menuitem', { name: 'Settings' }).click()
      await expect(page.getByRole('heading', { level: 1, name: 'Settings' })).toBeVisible()
      await page.getByRole('combobox', { name: 'Tags (optional)' }).fill('team')
      await page.keyboard.press('Enter')
      await page.getByRole('radio', { name: 'Delete it automatically on a date' }).check()
      await expect(page.getByLabel('Delete at the end of')).toBeVisible()
      await expectNoA11yViolations(page)
    })

    test("the copy dialog and a copy's provenance line", async ({ page }) => {
      await signUpThroughApi(page, uniqueEmail('a11y-copy'))
      const list = await createAccountList(page, 'Original list')
      await page.goto(`/l/${list.code}?dialog=copy`)
      const dialog = page.getByRole('dialog', { name: 'Make a copy' })
      await expect(dialog.getByRole('textbox', { name: 'Name of the copy' })).toBeVisible()
      await expectNoA11yViolations(page)
      await dialog.getByRole('button', { name: 'Make a copy' }).click()
      await expect(page.getByRole('heading', { level: 1, name: 'Original list (copy)' })).toBeVisible()
      await expect(page.getByRole('link', { name: 'Original list', exact: true })).toBeVisible()
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

      // Reporting (since 9.0), with the error for a missing reason showing.
      await page.getByRole('button', { name: 'List options' }).click()
      await page.getByRole('menuitem', { name: 'Report…' }).click()
      const report = page.getByRole('dialog', { name: 'Report this list' })
      await report.getByRole('button', { name: 'Send report' }).click()
      await expect(report.getByText('Choose what is wrong.')).toBeVisible()
      await expectNoA11yViolations(page)
      await report.getByRole('button', { name: 'Cancel' }).click()

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

    // Task 9.3: every route and state not covered above.

    test('email verification, both ways, and restoring an account', async ({ page }) => {
      const email = uniqueEmail('a11y-verify')
      await signUpThroughApi(page, email)
      await page.goto('/verify-email#key=not-a-real-key')
      await expect(page.getByRole('heading', { name: /expired or was already used|Couldn't verify/ })).toBeVisible()
      await expectNoA11yViolations(page)

      const link = new URL(linkIn(await emailTo(page.request, email, /confirm/i), '/verify-email'))
      await page.goto(link.pathname + link.hash)
      await expect(page.getByRole('heading', { name: 'Your email is verified' })).toBeVisible()
      await expectNoA11yViolations(page)

      const deleted = await page.request.fetch('/api/v2/me/', {
        method: 'DELETE',
        data: { confirm: email },
        headers: { 'X-CSRFToken': await csrfOf(page), Origin: new URL(page.url()).origin },
      })
      expect(deleted.status()).toBe(204)
      // Deleting signs out; signing in again within the grace period lands on the restore page.
      await page.goto('/signin')
      await page.getByRole('textbox', { name: 'Email' }).fill(email)
      await page.getByLabel('Password', { exact: true }).fill(PASSWORD)
      await page.getByRole('button', { name: 'Sign in' }).last().click()
      await expect(page.getByRole('heading', { level: 1, name: 'Your account is being deleted' })).toBeVisible()
      await expectNoA11yViolations(page)
    })

    test("an edit link that doesn't work, and new accounts' empty pages", async ({ page }) => {
      await page.goto('/l/AAAAAAAAAAAAAAAA/manage#t=not-a-token')
      await expect(page.getByRole('heading', { name: /edit link no longer works|doesn't exist/ })).toBeVisible()
      await expectNoA11yViolations(page)

      await signUpThroughApi(page, uniqueEmail('a11y-empty'))
      await page.goto('/lists')
      await expect(page.getByRole('heading', { level: 1, name: 'My lists' })).toBeVisible()
      await expectNoA11yViolations(page)
      await page.goto('/groups')
      await expect(page.getByRole('heading', { name: 'No groups yet' })).toBeVisible()
      await expectNoA11yViolations(page)
    })

    test('Explore with results, a tag filter, and no results', async ({ page }) => {
      const word = `zq${Date.now().toString(36)}${colorScheme}`
      await signUpVerified(page, uniqueEmail('a11y-explore'), 'Explorer')
      const { code } = await createAccountList(page, `${word} tools`)
      await apiAs(page, 'PATCH', `/api/v2/lists/${code}/`, { visibility: 'public', tags: ['a11y'] }, 200)
      await page.goto(`/explore?q=${word}&tags=a11y`)
      await expect(page.getByRole('list', { name: 'Public lists' }).getByRole('link')).toHaveText([`${word} tools`])
      await expectNoA11yViolations(page)
      await page.goto(`/explore?q=${word}-nothing`)
      await expect(page.getByRole('heading', { name: 'No lists match' })).toBeVisible()
      await expectNoA11yViolations(page)
    })

    test("a link's menu and dialogs, as its owner", async ({ page }) => {
      await signUpThroughApi(page, uniqueEmail('a11y-links'))
      const { code } = await createAccountList(page, 'Links to check')
      await createAccountList(page, 'Another list')
      for (const url of ['https://example.com/one', 'https://example.org/two']) {
        await apiAs(page, 'POST', `/api/v2/lists/${code}/links/`, { destination_url: url, title: url.slice(-3) })
      }
      await page.goto(`/l/${code}`)
      const menu = () => page.getByRole('button', { name: /^More actions for one/ })
      await menu().click()
      await expect(page.getByRole('menuitem', { name: 'Edit' })).toBeVisible()
      await expectNoA11yViolations(page)
      for (const [item, dialog] of [
        ['Edit', 'Edit link'],
        ['Details', 'Link details'],
        ['Move to position…', 'Move to position'],
        ['Move to another list…', 'Move to another list'],
      ] as const) {
        if (item !== 'Edit') await menu().click()
        await page.getByRole('menuitem', { name: item }).click()
        await expect(page.getByRole('dialog', { name: dialog })).toBeVisible()
        await expectNoA11yViolations(page)
        await page.keyboard.press('Escape')
        await expect(page.getByRole('dialog', { name: dialog })).toBeHidden()
      }
      await menu().click()
      await page.getByRole('menuitem', { name: 'Delete' }).click()
      await expect(page.getByRole('dialog', { name: 'Delete this link?' })).toBeVisible()
      await expectNoA11yViolations(page)
    })

    test("a group's settings and Share dialogs", async ({ page }) => {
      await signUpVerified(page, uniqueEmail('a11y-group-dialogs'), 'Group owner')
      const group = await apiAs(page, 'POST', '/api/v2/groups/', { title: 'Dialog group', tags: ['team'] })
      await page.goto(new URL(group.url).pathname)
      await page.getByRole('button', { name: 'More actions for the group Dialog group' }).click()
      await page.getByRole('menuitem', { name: 'Settings' }).click()
      await expect(page.getByRole('dialog', { name: 'Group settings' })).toBeVisible()
      await expectNoA11yViolations(page)
      await page.keyboard.press('Escape')
      await page.getByRole('button', { name: 'Share the group Dialog group' }).click()
      await expect(page.getByRole('dialog', { name: 'Share this group' })).toBeVisible()
      await expectNoA11yViolations(page)
    })
  })
}
