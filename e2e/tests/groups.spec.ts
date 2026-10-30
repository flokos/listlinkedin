// Groups (roadmap 4.3): building a workspace of lists, moving between them with the sidebar,
// reordering it without dragging, and scenario 3 in docs/v2/15-TEST-STRATEGY.md (the
// workspace on a phone: the drawer opens, switching lists moves focus to the list's <h1>,
// Escape closes it). A group shows each visitor only the lists they may see.
import { type Page } from '@playwright/test'

import {
  apiAs,
  createAccountList,
  expect,
  otherDevice,
  signUpThroughApi,
  test,
  uniqueEmail,
} from './fixtures'

/** The sidebar's links. On phones and tablets it is a drawer, opened with "Lists". */
async function openSidebar(page: Page, group: string, isMobile: boolean) {
  if (isMobile) await page.getByRole('button', { name: `Lists in ${group}` }).click()
  const nav = page.getByRole('navigation', { name: `Lists in ${group}` })
  await expect(nav).toBeVisible()
  return nav
}

async function groupWith(page: Page, title: string, lists: { title: string; visibility?: string }[]) {
  const group = await apiAs(page, 'POST', '/api/v2/groups/', { title, visibility: 'unlisted' })
  const codes: string[] = []
  for (const list of lists) {
    const created = await createAccountList(page, list.title)
    if (list.visibility) {
      await apiAs(page, 'PATCH', `/api/v2/lists/${created.code}/`, { visibility: list.visibility }, 200)
    }
    await apiAs(page, 'POST', `/api/v2/groups/${group.code}/lists/`, { list: created.code })
    codes.push(created.code)
  }
  return { group: group as { code: string; url: string }, codes }
}

test('create a group, add lists and move between them', async ({ page, isMobile }) => {
  await signUpThroughApi(page, uniqueEmail('group'))
  await createAccountList(page, 'Backend tools')
  await createAccountList(page, 'AI tools')

  await page.goto('/groups')
  await expect(page.getByRole('heading', { level: 1, name: 'Groups' })).toBeVisible()
  await page.getByRole('button', { name: 'New group' }).first().click()
  await page.getByRole('dialog').getByLabel('Name').fill('Dev Portal')
  await page.getByRole('button', { name: 'Create group' }).click()
  await expect(page).toHaveURL(/\/g\/[^/]+\/dev-portal$/)
  await expect(page.getByRole('heading', { level: 1, name: 'Dev Portal' })).toBeVisible()

  await page.getByRole('button', { name: 'Add your first list' }).click()
  const picker = page.getByRole('dialog', { name: 'Add lists to the group' })
  await picker.getByText('Backend tools', { exact: true }).click()
  await expect(picker.getByText('In this group')).toHaveCount(1)
  await picker.getByText('AI tools', { exact: true }).click()
  await expect(picker.getByText('In this group')).toHaveCount(2)
  await picker.getByRole('button', { name: 'Done' }).click()

  // The first list is shown; the group's name is no longer the heading.
  await expect(page.getByRole('heading', { level: 1, name: 'Backend tools' })).toBeVisible()
  const nav = await openSidebar(page, 'Dev Portal', isMobile)
  await expect(nav.getByRole('link')).toHaveText([/Backend tools/, /AI tools/])
  await nav.getByRole('link', { name: 'AI tools' }).click()
  await expect(page).toHaveURL(/\/g\/[^/]+\/l\/[^/]+$/)
  await expect(page.getByRole('heading', { level: 1, name: 'AI tools' })).toBeFocused()
  await expect(page).toHaveTitle('AI tools · Dev Portal · listlinkedin')

  // Back returns to the previous list.
  await page.goBack()
  await expect(page.getByRole('heading', { level: 1, name: 'Backend tools' })).toBeVisible()
  await page.goto('/groups')
  await expect(page.getByRole('link', { name: 'Dev Portal' })).toBeVisible()
  await expect(page.getByText('2 lists')).toBeVisible()
})

test('the workspace on a phone: drawer, focus and Escape', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'the drawer is modal on phones; desktops have a permanent sidebar')
  await signUpThroughApi(page, uniqueEmail('phone'))
  const { group } = await groupWith(page, 'Dev Portal', [{ title: 'Backend tools' }, { title: 'AI tools' }])
  await page.goto(new URL(group.url).pathname)
  await expect(page.getByRole('heading', { level: 1, name: 'Backend tools' })).toBeVisible()

  const opener = page.getByRole('button', { name: 'Lists in Dev Portal' })
  await opener.click()
  const drawer = page.getByRole('dialog', { name: 'Lists in Dev Portal' })
  await expect(drawer).toBeVisible()
  // Focus moves in, onto the list shown now.
  await expect(drawer.getByRole('link', { name: 'Backend tools' })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(drawer).toBeHidden()
  await expect(opener).toBeFocused()

  await opener.click()
  await drawer.getByRole('link', { name: 'AI tools' }).click()
  await expect(drawer).toBeHidden()
  await expect(page.getByRole('heading', { level: 1, name: 'AI tools' })).toBeFocused()
})

test('reorder the sidebar without dragging; the order persists', async ({ page, isMobile }) => {
  await signUpThroughApi(page, uniqueEmail('order'))
  const { group } = await groupWith(page, 'Team', [
    { title: 'Alpha' },
    { title: 'Bravo' },
    { title: 'Charlie' },
  ])
  await page.goto(new URL(group.url).pathname)
  await expect(page.getByRole('heading', { level: 1, name: 'Alpha' })).toBeVisible()

  await page.getByRole('button', { name: 'More actions for the group Team' }).click()
  await page.getByRole('menuitem', { name: 'Reorder lists' }).click()
  await expect(page.getByRole('button', { name: 'Move Alpha up' })).toBeDisabled()
  await page.getByRole('button', { name: 'Move Charlie up' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Charlie moved to position 2 of 3.' })).toBeAttached()
  await page.getByRole('button', { name: 'Done' }).click()

  await page.reload()
  const nav = await openSidebar(page, 'Team', isMobile)
  await expect(nav.getByRole('link')).toHaveText([/Alpha/, /Charlie/, /Bravo/])
})

test('visitors see only the lists they may open', async ({ page, browser, baseURL, isMobile }) => {
  await signUpThroughApi(page, uniqueEmail('owner'))
  const { group } = await groupWith(page, 'Mixed', [
    { title: 'Open tools', visibility: 'unlisted' },
    { title: 'Secret plans' }, // private
  ])
  // The owner sees both, with the private one marked as not shown to everyone.
  await page.goto(new URL(group.url).pathname)
  const own = await openSidebar(page, 'Mixed', isMobile)
  await expect(own.getByRole('link')).toHaveText([/Open tools/, /Secret plans/])
  await expect(own.getByRole('link', { name: /Secret plans/ })).toContainText('not everyone')

  // Someone with the link sees the unlisted list only, and nothing about the other one.
  const visitor = await otherDevice(browser, baseURL)
  await visitor.page.goto(new URL(group.url).pathname)
  await expect(visitor.page.getByRole('heading', { level: 1, name: 'Open tools' })).toBeVisible()
  const nav = await openSidebar(visitor.page, 'Mixed', isMobile)
  await expect(nav.getByRole('link')).toHaveText([/Open tools/])
  await expect(visitor.page.getByText('Secret plans')).toHaveCount(0)
  expect(await visitor.page.content()).not.toContain('Secret plans')
  await visitor.context.close()
})

test('a private group is "not found" for others', async ({ page, browser, baseURL }) => {
  await signUpThroughApi(page, uniqueEmail('private'))
  const group = await apiAs(page, 'POST', '/api/v2/groups/', { title: 'Hidden' })
  const visitor = await otherDevice(browser, baseURL)
  await visitor.page.goto(new URL(group.url).pathname)
  await expect(visitor.page.getByRole('heading', { level: 1, name: "This group doesn't exist" })).toBeVisible()
  await expect(visitor.page.getByText('Hidden')).toHaveCount(0)
  await visitor.context.close()
})

test('on a tablet the sidebar is a rail that opens on focus', async ({ page, isMobile }) => {
  test.skip(isMobile, 'phones get the modal drawer')
  await page.setViewportSize({ width: 1100, height: 800 })
  await signUpThroughApi(page, uniqueEmail('rail'))
  const { group } = await groupWith(page, 'Rail', [{ title: 'Backend tools' }, { title: 'AI tools' }])
  await page.goto(new URL(group.url).pathname)
  await expect(page.getByRole('heading', { level: 1, name: 'Backend tools' })).toBeVisible()

  const drawer = page.locator('.ll-group-sidebar')
  await expect(drawer).not.toHaveClass(/v-navigation-drawer--expanded/)
  const nav = page.getByRole('navigation', { name: 'Lists in Rail' })
  await nav.getByRole('link', { name: 'AI tools' }).focus()
  await expect(drawer).toHaveClass(/v-navigation-drawer--expanded/)
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { level: 1, name: 'AI tools' })).toBeFocused()
  await expect(drawer).not.toHaveClass(/v-navigation-drawer--expanded/) // focus left it

  // Touch screens have no hover: the toggle shows the names.
  const toggle = page.getByRole('button', { name: 'Show list names' })
  await toggle.click()
  await expect(drawer).toHaveClass(/v-navigation-drawer--expanded/)
  await expect(page.getByRole('button', { name: 'Hide list names' })).toHaveAttribute('aria-expanded', 'true')
})
