import { readFile } from 'node:fs/promises'

import { expect, openAsOwner, otherDevice, test } from './fixtures'

test('My lists shows live status, and a backup restores access on another device', async ({
  page,
  browser,
  baseURL,
  api,
}) => {
  const keep = await api.createList('Backup keeper')
  const gone = await api.createList('Backup goner')
  await openAsOwner(page, keep)
  await openAsOwner(page, gone)

  await page.goto('/lists')
  const main = page.locator('main')
  await expect(main.getByRole('link', { name: 'Backup keeper' })).toBeVisible()
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Download backup' }).click(),
  ])
  expect(download.suggestedFilename()).toMatch(/^listlinkedin-saved-lists-\d{4}-\d{2}-\d{2}\.json$/)
  const file = (await download.path())!
  const backup = JSON.parse(await readFile(file, 'utf8'))
  expect(backup.lists).toHaveLength(2)

  // A list deleted elsewhere is marked as such, with a way to remove it.
  await api.deleteList(gone)
  await page.reload()
  await expect(main.getByText('Deleted', { exact: true })).toBeVisible()

  // A fresh device restores the backup.
  const phone = await otherDevice(browser, baseURL)
  await phone.page.goto('/lists')
  await expect(phone.page.getByText('No lists on this device yet')).toBeVisible()
  await phone.page.locator('input[type=file]').setInputFiles(file)
  const summary = phone.page.getByRole('status').filter({ hasText: '1 list no longer exists.' })
  await expect(summary).toContainText('Restored 1 list')
  await expect(phone.page.locator('main').getByRole('link', { name: 'Backup keeper' })).toBeVisible()

  // Restoring again adds nothing.
  await phone.page.locator('input[type=file]').setInputFiles(file)
  await expect(phone.page.getByText('Nothing new to restore')).toBeVisible()
  await expect(phone.page.getByText('1 list is already saved here.')).toBeVisible()

  await phone.page.goto(`/l/${keep.public_code}`)
  await expect(phone.page.getByText('Your list', { exact: true })).toBeVisible()
  await phone.context.close()
})

test('a file without edit links is rejected clearly', async ({ page }) => {
  await page.goto('/lists')
  await page.locator('input[type=file]').setInputFiles({
    name: 'notes.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('just some notes'),
  })
  await expect(page.getByText('No lists found in that file')).toBeVisible()
})
