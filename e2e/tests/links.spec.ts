import { cardTitle, cardTitles, expect, openAsOwner, test } from './fixtures'

test.describe('managing links as the owner', () => {
  test('adds links, catching mistakes before and after the server', async ({ page, api }) => {
    const list = await api.createList('Links')
    await openAsOwner(page, list)
    const url = page.getByRole('textbox', { name: 'Link', exact: true })
    const title = page.getByRole('textbox', { name: 'Title (optional)' })
    const add = page.getByRole('button', { name: 'Add link' })

    // A bare host gets https:// added.
    await url.fill('example.com/guide')
    await title.fill('The guide')
    await add.click()
    await expect(page.getByText('Link added')).toBeVisible()
    await expect(cardTitle(page, 'The guide')).toBeVisible()
    await expect(page.getByText('example.com/guide', { exact: true })).toBeVisible()
    await expect(url).toHaveValue('') // cleared for the next one
    await expect(url).toBeFocused()

    for (const [bad, message] of [
      ['ftp://files.example.com', 'Only http and https links are allowed.'],
      ['https://user:secret@example.com/', "Links can't contain a username or password."],
    ]) {
      await url.fill(bad)
      await add.click()
      await expect(page.getByText(message)).toBeVisible()
    }

    // Duplicate after the server's normalization: reported under the URL field.
    await url.fill('HTTPS://EXAMPLE.COM/guide')
    await add.click()
    await expect(page.getByText('This URL is already in the list.')).toBeVisible()
    await expect(page.getByText('1 link', { exact: true })).toBeVisible()
  })

  test('edits a link without changing its short URL, and deletes after confirming', async ({ page, api }) => {
    const list = await api.createList('Edit and delete')
    const link = await api.addLink(list, 'https://example.com/old', 'Old title')
    await openAsOwner(page, list)

    await page.getByRole('button', { name: 'More actions for Old title' }).click()
    await page.getByRole('menuitem', { name: 'Edit' }).click()
    const dialog = page.getByRole('dialog', { name: 'Edit link' })
    await dialog.getByRole('textbox', { name: 'Link', exact: true }).fill('https://example.com/new')
    await dialog.getByRole('textbox', { name: 'Title (optional)' }).fill('New title')
    await dialog.getByRole('button', { name: 'Save changes' }).click()
    await expect(page.getByText('Link updated')).toBeVisible()
    const card = cardTitle(page, 'New title')
    await expect(card).toHaveAttribute('href', link.short_url)

    // The short URL now redirects to the new destination.
    const response = await page.request.get(link.short_url, { maxRedirects: 0 })
    expect(response.status()).toBe(302)
    expect(response.headers().location).toBe('https://example.com/new')

    await page.getByRole('button', { name: 'More actions for New title' }).click()
    await page.getByRole('menuitem', { name: 'Delete' }).click()
    await page.getByRole('button', { name: 'Delete link' }).click()
    await expect(page.getByText('Link deleted')).toBeVisible()
    await expect(page.getByText('Add your first link')).toBeVisible()
    expect((await page.request.get(link.short_url, { maxRedirects: 0 })).status()).toBe(404)
  })

  test('searches and sorts links', async ({ page, api, isMobile }) => {
    const list = await api.createList('Search')
    await api.addLink(list, 'https://zebra.example/', 'Zebra crossing')
    await api.addLink(list, 'https://apple.example/', 'Apple pie')
    await api.addLink(list, 'https://mango.example/', 'Mango season')
    await page.goto(`/l/${list.public_code}`)

    const titles = cardTitles(page)
    await expect(titles).toHaveText([/Mango/, /Apple/, /Zebra/]) // newest first
    await page.getByRole('button', { name: 'A–Z' }).click()
    await expect(titles).toHaveText([/Apple/, /Mango/, /Zebra/])

    const search = page.getByRole('textbox', { name: 'Search links' })
    if (isMobile) await search.click()
    else await page.keyboard.press('/') // shortcut focuses search
    await expect(search).toBeFocused()
    await page.keyboard.type('zeb')
    await expect(titles).toHaveText([/Zebra/])
    await search.fill('nothing like this')
    await expect(page.getByText('No matching links')).toBeVisible()
    await page.getByRole('button', { name: 'Clear search' }).click()
    await expect(titles).toHaveCount(3)
  })
})

test('short URLs redirect visitors to the destination', async ({ api, request }) => {
  const list = await api.createList('Redirects')
  const link = await api.addLink(list, 'https://example.org/target')
  const response = await request.get(link.short_url, { maxRedirects: 0 })
  expect(response.status()).toBe(302)
  expect(response.headers()).toMatchObject({
    location: 'https://example.org/target',
    'cache-control': 'no-store',
    'referrer-policy': 'no-referrer',
  })
})
