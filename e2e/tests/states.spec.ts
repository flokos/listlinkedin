// Error and edge states, with server responses mocked where the real stack can't easily
// produce them. Chromium only (playwright.config.ts): this is app logic, not engine behaviour.
import { expect, openAsOwner, test } from './fixtures'

test('unknown lists get a not-found page', async ({ page }) => {
  await page.goto('/l/NoSuchList000000')
  await expect(page.getByRole('heading', { level: 1, name: "This list doesn't exist" })).toBeVisible()
  await expect(page).toHaveTitle('List not found · listlinkedin')
  await page.getByRole('link', { name: 'Create a new list' }).click()
  await expect(page.getByRole('textbox', { name: 'List name' })).toBeFocused()
})

test('expired lists explain what happened', async ({ page, api }) => {
  const list = await api.createList('Expired')
  await page.route(`**/api/v1/lists/${list.public_code}/**`, (route) =>
    route.fulfill({ status: 410, json: { detail: 'This list has expired.' } }),
  )
  await page.goto(`/l/${list.public_code}`)
  await expect(page.getByRole('heading', { level: 1, name: 'This list has expired' })).toBeVisible()
  await expect(page).toHaveTitle('List expired · listlinkedin')
})

test('rate-limited list creation shows the wait and disables the button', async ({ page }) => {
  await page.route('**/api/v1/lists/', (route) =>
    route.request().method() === 'POST'
      ? route.fulfill({ status: 429, headers: { 'Retry-After': '120' }, json: { detail: 'Request was throttled.' } })
      : route.continue(),
  )
  await page.goto('/')
  await page.getByRole('textbox', { name: 'List name' }).fill('Too many')
  await page.getByRole('button', { name: 'Create list' }).click()
  await expect(page.getByText("You've created a lot of lists. Try again in 2 min.")).toBeVisible()
  await expect(page.getByRole('button', { name: 'Create list' })).toBeDisabled()
})

test('a server error offers a retry that recovers', async ({ page, api }) => {
  const list = await api.createList('Flaky server')
  let failures = 1
  await page.route(`**/api/v1/lists/${list.public_code}/`, (route) =>
    failures-- > 0 ? route.fulfill({ status: 502, body: 'Bad gateway' }) : route.continue(),
  )
  await page.goto(`/l/${list.public_code}`)
  await expect(page.getByRole('heading', { level: 1, name: "Couldn't load this list" })).toBeVisible()
  await expect(page.getByText('Something went wrong on our side. Please try again.')).toBeVisible()
  await page.getByRole('button', { name: 'Try again' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Flaky server' })).toBeVisible()
})

test('going offline shows a banner and failed saves explain why', async ({ page, context, api }) => {
  const list = await api.createList('Offline')
  await openAsOwner(page, list)
  await context.setOffline(true)
  await expect(page.getByText("You're offline. Changes can't be saved until you reconnect.")).toBeVisible()
  await page.getByRole('textbox', { name: 'Link', exact: true }).fill('https://example.com/offline')
  await page.getByRole('button', { name: 'Add link' }).click()
  await expect(page.getByText('Could not reach the server. Check your connection and try again.')).toBeVisible()
  await context.setOffline(false)
  await expect(page.getByText("You're offline.")).toBeHidden()
  await page.getByRole('button', { name: 'Add link' }).click()
  await expect(page.getByText('Link added')).toBeVisible()
})

test('a page chunk missing after a deploy reloads the app once instead of breaking', async ({
  page,
  consoleErrors,
}) => {
  await page.goto('/')
  // Until the app reloads, the About page's chunk is gone (as after a deploy). Vite also
  // preloads it, so every request fails, not just the first.
  let reloaded = false
  let failedRequests = 0
  page.on('load', () => (reloaded = true))
  await page.route('**/assets/AboutView-*.js', (route) => {
    if (reloaded) return route.continue()
    failedRequests++
    return route.fulfill({ status: 404, body: 'Not found' })
  })
  await page.locator('header').getByRole('link', { name: 'About' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'About & privacy' })).toBeVisible()
  expect(failedRequests).toBeGreaterThan(0)
  expect(reloaded).toBe(true)
  await expect(page).toHaveURL('/about')
  // The failed import is logged by the browser; it is the scenario under test.
  consoleErrors.splice(0)
})
