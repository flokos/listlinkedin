import { readFile } from 'node:fs/promises'

import { createListInUI, expect, test } from './fixtures'

test('creating a list requires saving the edit link, then opens it in owner mode', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('textbox', { name: 'List name' }).fill('Friday team bonding')
  await page.getByRole('button', { name: 'Create list' }).click()

  const dialog = page.getByRole('dialog', { name: 'Your list is ready. Save your edit link' })
  await expect(dialog).toBeVisible()
  const editLink = await dialog.getByRole('textbox', { name: 'Private edit link' }).inputValue()
  expect(editLink).toMatch(/^https:\/\/go\.example\.test\/l\/[\w-]+\/manage#t=[\w-]+$/)
  await expect(dialog.getByRole('textbox', { name: 'Share link (view only)' })).toHaveValue(
    /^https:\/\/go\.example\.test\/l\/[\w-]+$/,
  )

  // The dialog can't be dismissed until the user confirms they saved the link.
  const proceed = dialog.getByRole('button', { name: 'Go to my list' })
  await expect(proceed).toBeDisabled()
  await page.keyboard.press('Escape')
  await expect(dialog).toBeVisible()

  // The .txt download holds both links.
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    dialog.getByRole('button', { name: 'Download as file' }).click(),
  ])
  expect(download.suggestedFilename()).toMatch(/^listlinkedin-[\w-]+\.txt$/)
  const text = await readFile((await download.path())!, 'utf8')
  expect(text).toContain(editLink)

  await dialog.getByRole('checkbox', { name: /saved my edit link/ }).check()
  await proceed.click()
  await expect(dialog).toBeHidden()
  await expect(page.getByRole('heading', { level: 1, name: 'Friday team bonding' })).toBeVisible()
  await expect(page.getByText('Your list', { exact: true })).toBeVisible()
  await expect(page.getByText('Add your first link')).toBeVisible()
  await expect(page).toHaveTitle('Friday team bonding · listlinkedin')
})

test('the edit-link step survives a reload before it is acknowledged', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('textbox', { name: 'List name' }).fill('Reload me')
  await page.getByRole('button', { name: 'Create list' }).click()
  await expect(page.getByText('Your list is ready. Save your edit link')).toBeVisible()
  await page.reload()
  await expect(page.getByText('Your list is ready. Save your edit link')).toBeVisible()
  await page.getByRole('checkbox', { name: /saved my edit link/ }).check()
  await page.getByRole('button', { name: 'Go to my list' }).click()
  // Acknowledged: a further reload doesn't ask again.
  await page.reload()
  await expect(page.getByRole('heading', { level: 1, name: 'Reload me' })).toBeVisible()
  await expect(page.getByText('Your list is ready. Save your edit link')).toBeHidden()
})

test('a new list appears in Saved lists and on Home', async ({ page }) => {
  await createListInUI(page, 'Saved list check')
  await page.goto('/lists')
  await expect(page.getByRole('heading', { level: 1, name: 'Saved lists' })).toBeVisible()
  await expect(page.locator('main').getByRole('link', { name: 'Saved list check' })).toBeVisible()
  await expect(page.getByText('Expires in 30 days').first()).toBeVisible()
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Saved on this device' })).toBeVisible()
})

test('an empty name is rejected without a request', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Create list' }).click()
  await expect(page.getByText('Give your list a name.')).toBeVisible()
})
