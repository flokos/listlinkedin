// Groups from the extension's popup (task 11.8): making a group, the lists in it and their
// order, its name, and deleting it. A group never changes a list: the lists are checked to
// be as they were.
import type { Page } from '@playwright/test'

import { createAccountList, signUpThroughApi, uniqueEmail } from '../fixtures'
import { connectFrom, expect, popupAbout, test, welcomePage } from './fixtures'

const groupsOf = async (page: Page): Promise<{ code: string; title: string; visibility: string }[]> =>
  (await (await page.request.get('/api/v2/groups/')).json()).results

const listsIn = async (page: Page, code: string): Promise<string[]> =>
  (await (await page.request.get(`/api/v2/groups/${code}/lists/`)).json()).map(
    (list: { title: string }) => list.title,
  )

test('make a group, fill and order it, rename it and delete it, from the popup', async ({
  context,
  extensionId,
  page,
}) => {
  await signUpThroughApi(page, uniqueEmail('ext-groups'))
  const reading = await createAccountList(page, 'Reading')
  await createAccountList(page, 'Work')
  await page.goto('/')
  await connectFrom(await welcomePage(context))

  const popup = await popupAbout(context, extensionId, 'http://fixture.test/', 'A page')
  await popup.getByRole('button', { name: 'My lists' }).click()

  // A new group is private unless the user says otherwise.
  await popup.getByRole('button', { name: 'New group' }).click()
  await expect(popup.getByLabel('Who can open it')).toHaveValue('private')
  await popup.getByLabel("New group's name").fill('Team')
  await popup.getByRole('button', { name: 'Create group' }).click()
  await expect(popup.getByRole('heading', { level: 2, name: 'Group: Team' })).toBeVisible()
  const [group] = await groupsOf(page)
  expect(group).toMatchObject({ title: 'Team', visibility: 'private' })

  // Two lists into it.
  for (const title of ['Reading', 'Work']) {
    await popup.getByLabel('Add a list').selectOption({ label: title })
    await popup.getByRole('button', { name: 'Add', exact: true }).click()
    await expect(popup.getByRole('status')).toHaveText(`Added “${title}” to the group.`)
  }
  expect(await listsIn(page, group!.code)).toEqual(['Reading', 'Work'])

  // Another order: by the keyboard, then by dragging.
  await popup.getByRole('button', { name: 'Move Work up' }).focus()
  await popup.keyboard.press('Enter')
  await expect(popup.getByRole('status')).toHaveText('“Work” is now 1 of 2.')
  await expect(popup.getByRole('button', { name: 'Move Work down' })).toBeFocused() // it reached the top
  expect(await listsIn(page, group!.code)).toEqual(['Work', 'Reading'])
  const row = (title: string) => popup.locator('.manage__list').filter({ hasText: title })
  await row('Work').dragTo(row('Reading'))
  await expect(popup.getByRole('status')).toHaveText('“Work” is now 2 of 2.')
  expect(await listsIn(page, group!.code)).toEqual(['Reading', 'Work'])

  // Its name.
  await popup.getByLabel('Name', { exact: true }).fill('Crew')
  await popup.getByRole('button', { name: 'Rename' }).click()
  await expect(popup.getByRole('status')).toHaveText('The group is now called “Crew”.')
  expect((await groupsOf(page))[0]!.title).toBe('Crew')

  // A list out of it: asked first, and the list itself stays.
  await popup.getByRole('button', { name: 'Take Work out…' }).click()
  await popup.getByRole('button', { name: 'Take Work out of the group' }).click()
  await expect(popup.getByRole('status')).toContainText('“Work” is no longer in the group.')
  expect(await listsIn(page, group!.code)).toEqual(['Reading'])

  // Back among the lists, the group shows what was done.
  await popup.getByRole('button', { name: 'Done' }).click()
  await expect(popup.getByText('1 list ·')).toBeVisible()
  await expect(popup.locator('.browse__title')).toHaveText(['Reading'])

  // Deleting the group: asked first. The lists are as they were.
  await popup.getByRole('button', { name: 'Edit group' }).click()
  await popup.getByRole('button', { name: 'Delete group…' }).click()
  await popup.getByRole('button', { name: 'Delete group', exact: true }).click()
  await expect(popup.getByRole('status')).toHaveText('The group “Crew” is deleted. Its lists are as they were.')
  expect(await groupsOf(page)).toEqual([])
  await expect(popup.locator('.browse__title')).toHaveText(['Work', 'Reading'])
  const list = await (await page.request.get(`/api/v2/lists/${reading.code}/`)).json()
  expect(list).toMatchObject({ title: 'Reading', visibility: 'private' })
})
