// Reordering links (roadmap 2.5, e2e scenario 4 in docs/v2/15-TEST-STRATEGY.md): dragging on a
// desktop, long-press dragging on a touch screen, and the ⋮ Move items, which work everywhere
// without dragging (WCAG 2.2 SC 2.5.7). The order is stored, so it survives a reload, and
// every move is announced to screen readers.
import { type Page } from '@playwright/test'

import {
  cardTitle,
  cardTitles,
  createAccountList,
  type CreatedList,
  expect,
  openAsOwner,
  signUpVerified,
  test,
  uniqueEmail,
} from './fixtures'

async function listWith(api: { createList: (t: string) => Promise<CreatedList>; addLink: (l: CreatedList, u: string, t?: string) => Promise<unknown> }, names: string[]) {
  const list = await api.createList('Reorder')
  for (const name of names) await api.addLink(list, `https://${name.toLowerCase()}.example/`, name)
  return list
}

const tile = (page: Page, name: string) => page.getByRole('article').filter({ has: cardTitle(page, name) })
const announced = (page: Page, text: string) => page.getByRole('status').filter({ hasText: text })

test('drag a tile to a new place with the mouse', async ({ page, api, isMobile }) => {
  test.skip(isMobile, 'mouse dragging is a desktop concern; phones are covered below')
  const list = await listWith(api, ['Alpha', 'Bravo', 'Charlie', 'Delta'])
  await openAsOwner(page, list)
  await expect(cardTitles(page)).toHaveText([/Alpha/, /Bravo/, /Charlie/, /Delta/])

  const from = (await tile(page, 'Alpha').boundingBox())!
  const to = (await tile(page, 'Charlie').boundingBox())!
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2)
  await page.mouse.down()
  await page.mouse.move(from.x + from.width / 2 + 10, from.y + from.height / 2 + 5, { steps: 5 })
  await page.mouse.move(to.x + to.width / 2 + 20, to.y + to.height / 2, { steps: 20 })
  await page.mouse.up()

  await expect(cardTitles(page)).toHaveText([/Bravo/, /Charlie/, /Alpha/, /Delta/])
  await expect(announced(page, 'Alpha moved to position 3 of 4.')).toBeAttached()
  expect(page.context().pages()).toHaveLength(1) // the drop didn't also open the link
  await page.reload()
  await expect(cardTitles(page)).toHaveText([/Bravo/, /Charlie/, /Alpha/, /Delta/])
})

test('move with the ⋮ menu, without dragging', async ({ page, api }) => {
  const list = await listWith(api, ['Alpha', 'Bravo', 'Charlie'])
  await openAsOwner(page, list)

  await page.getByRole('button', { name: 'More actions for Bravo' }).click()
  await page.getByRole('menuitem', { name: 'Move up' }).click()
  await expect(cardTitles(page)).toHaveText([/Bravo/, /Alpha/, /Charlie/])
  await expect(announced(page, 'Bravo moved to position 1 of 3.')).toBeAttached()

  await page.getByRole('button', { name: 'More actions for Bravo' }).click()
  await expect(page.getByRole('menuitem', { name: 'Move up' })).toBeDisabled() // already first
  await page.getByRole('menuitem', { name: 'Move to position…' }).click()
  const dialog = page.getByRole('dialog', { name: 'Move to position' })
  const position = dialog.getByRole('spinbutton', { name: 'Position' })
  await expect(position).toBeFocused()
  await position.fill('3')
  await dialog.getByRole('button', { name: 'Move' }).click()
  await expect(cardTitles(page)).toHaveText([/Alpha/, /Charlie/, /Bravo/])

  await page.reload()
  await expect(cardTitles(page)).toHaveText([/Alpha/, /Charlie/, /Bravo/])

  // Sorted or filtered views aren't the stored order: no Move items there.
  await page.getByRole('button', { name: /^Sort: / }).click()
  await page.getByRole('menuitemradio', { name: 'A–Z' }).click()
  await page.getByRole('button', { name: 'More actions for Charlie' }).click()
  await expect(page.getByRole('menuitem', { name: 'Details' })).toBeVisible()
  await expect(page.getByRole('menuitem', { name: 'Move up' })).toHaveCount(0)
})

test('move with the keyboard only', async ({ page, api, isMobile }) => {
  test.skip(isMobile, 'keyboard navigation is a desktop concern')
  const list = await listWith(api, ['Alpha', 'Bravo', 'Charlie'])
  await openAsOwner(page, list)

  const menu = page.getByRole('button', { name: 'More actions for Charlie' })
  await menu.focus()
  await page.keyboard.press('Enter')
  const toTop = page.getByRole('menuitem', { name: 'Move to top' })
  await expect(toTop).toBeVisible()
  for (let i = 0; i < 12 && !(await toTop.evaluate((el) => el.contains(document.activeElement))); i++) {
    await page.keyboard.press('ArrowDown')
  }
  await page.keyboard.press('Enter')
  await expect(cardTitles(page)).toHaveText([/Charlie/, /Alpha/, /Bravo/])
  await expect(announced(page, 'Charlie moved to position 1 of 3.')).toBeAttached()
  await expect(menu).toBeFocused() // back on the moved link's menu button
})

test('long-press and drag on a touch screen', async ({ page, api, isMobile, browserName }) => {
  test.skip(!isMobile || browserName !== 'chromium', 'touch input is sent through Chromium DevTools')
  const list = await listWith(api, ['Alpha', 'Bravo', 'Charlie', 'Delta'])
  await openAsOwner(page, list)
  await expect(cardTitles(page)).toHaveCount(4)

  const cdp = await page.context().newCDPSession(page)
  const touch = (type: 'touchStart' | 'touchMove' | 'touchEnd', x = 0, y = 0) =>
    cdp.send('Input.dispatchTouchEvent', { type, touchPoints: type === 'touchEnd' ? [] : [{ x, y }] })
  await tile(page, 'Alpha').scrollIntoViewIfNeeded()
  const from = (await tile(page, 'Alpha').boundingBox())!
  const to = (await tile(page, 'Bravo').boundingBox())!
  const [x0, y0] = [from.x + from.width / 2, from.y + from.height / 2]
  const [x1, y1] = [to.x + to.width / 2 + 10, to.y + to.height / 2]
  await touch('touchStart', x0, y0)
  await page.waitForTimeout(400) // a long press: shorter touches scroll the page instead
  for (let i = 1; i <= 20; i++) {
    await touch('touchMove', x0 + ((x1 - x0) * i) / 20, y0 + ((y1 - y0) * i) / 20)
    await page.waitForTimeout(16)
  }
  await touch('touchEnd')
  await expect(cardTitles(page)).toHaveText([/Bravo/, /Alpha/, /Charlie/, /Delta/])
  await page.reload()
  await expect(cardTitles(page)).toHaveText([/Bravo/, /Alpha/, /Charlie/, /Delta/])
})

test('move a link to another of your lists', async ({ page }) => {
  await signUpVerified(page, uniqueEmail('mover'), 'Mover')
  const source = await createAccountList(page, 'Inbox')
  const target = await createAccountList(page, 'Archive')
  await page.goto(`/l/${source.code}`)
  await page.getByRole('textbox', { name: 'Link', exact: true }).fill('https://example.com/keep')
  await page.getByRole('textbox', { name: 'Title (optional)' }).fill('Keeper')
  await page.getByRole('button', { name: 'Add link' }).click()
  await expect(cardTitle(page, 'Keeper')).toBeVisible()
  const oldShortUrl = await cardTitle(page, 'Keeper').getAttribute('href')

  await page.getByRole('button', { name: 'More actions for Keeper' }).click()
  await page.getByRole('menuitem', { name: 'Move to another list…' }).click()
  const picker = page.getByRole('dialog', { name: 'Move to another list' })
  await picker.getByText('Archive', { exact: true }).click()
  await expect(cardTitle(page, 'Keeper')).toBeHidden()

  await page.goto(`/l/${target.code}`)
  await expect(cardTitle(page, 'Keeper')).toBeVisible()
  expect((await page.request.get(oldShortUrl!, { maxRedirects: 0 })).status()).toBe(404)
})
