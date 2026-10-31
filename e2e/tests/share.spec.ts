import { expect, test } from './fixtures'

test('sharing shows the view link and a QR code, and Back closes the dialog', async ({
  page,
  api,
  browserName,
  context,
}) => {
  const list = await api.createList('Share me')
  await page.goto(`/l/${list.public_code}`)
  await page.getByRole('button', { name: 'Share', exact: true }).click()
  await expect(page).toHaveURL(/\?dialog=share$/)

  const dialog = page.getByRole('dialog', { name: 'Share this list' })
  await expect(dialog.getByRole('textbox', { name: 'Share link' })).toHaveValue(`${list.public_url}/share-me`)
  const qr = dialog.getByRole('img', { name: /QR code/ })
  await expect(qr).toHaveAttribute('src', /^data:image\/png;base64,/)
  expect(await qr.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(100)

  if (browserName === 'chromium') await context.grantPermissions(['clipboard-read', 'clipboard-write'])
  await dialog.getByRole('button', { name: 'Copy share link' }).click()
  await expect(page.getByText('Share link copied to clipboard')).toBeVisible()
  if (browserName === 'chromium') {
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(`${list.public_url}/share-me`)
  }

  await page.goBack()
  await expect(dialog).toBeHidden()
  await expect(page).toHaveURL(`/l/${list.public_code}`)
  await expect(page).toHaveTitle('Share me · listlinkedin')
})
