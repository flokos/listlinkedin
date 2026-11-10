// Connecting a browser (docs/v2/adr/ADR-020): the extension opens /connect-browser, the user
// approves, the page hands the extension a one-time code, and the extension stays signed in
// until it is disconnected. The tests play the extension's part (fixtures.ts): its content
// script in the page, and the exchange of the code. The extension itself has its own suite.
import {
  connectBrowser,
  emailTo,
  expect,
  extensionSays,
  handedCode,
  PASSWORD,
  pkce,
  playExtension,
  signUpThroughApi,
  test,
  uniqueEmail,
} from './fixtures'

const connectUrl = (challenge: string, name = 'Firefox on Linux') =>
  `/connect-browser?challenge=${challenge}&name=${encodeURIComponent(name)}`
const heading = (name: string | RegExp) => ({ level: 1, name }) as const

test('approve a browser, use its token, then disconnect it from the account page', async ({ page, request }) => {
  const email = uniqueEmail('connect')
  await signUpThroughApi(page, email)
  const { verifier, challenge } = pkce()
  await playExtension(page, challenge)

  await page.goto(connectUrl(challenge))
  await expect(page.getByRole('heading', heading('Connect this browser?'))).toBeVisible()
  await expect(page.locator('dd')).toHaveText(['Firefox on Linux', email])
  await page.getByRole('button', { name: 'Connect', exact: true }).click()

  // The code reaches the extension through the page, never through the address bar.
  const code = await handedCode(page)
  expect(page.url()).not.toContain(code)
  const wrong = await request.post('/api/v2/browsers/connect/', { data: { code, verifier: pkce().verifier } })
  expect(wrong.status()).toBe(400)
  const exchange = await request.post('/api/v2/browsers/connect/', { data: { code, verifier } })
  expect(exchange.status(), await exchange.text()).toBe(201)
  const { session_token: token } = await exchange.json()
  await extensionSays(page, challenge, 'connected')
  await expect(page.getByRole('heading', heading('This browser is connected'))).toBeVisible()
  await expect(page.getByText(code)).toHaveCount(0)

  // The token signs in as the account, with no cookie and no CSRF token.
  const extension = { headers: { 'X-Session-Token': token } }
  expect((await (await request.get('/api/v2/me/', extension)).json()).email).toBe(email)
  const saved = await request.post('/api/v2/lists/', { data: { title: 'From the extension' }, ...extension })
  expect(saved.status(), await saved.text()).toBe(201)
  expect((await request.post('/api/v2/browsers/connect/', { data: { code, verifier } })).status()).toBe(400)
  // The account hears about it by email.
  expect(await emailTo(request, email, /browser was connected/i)).toContain('Firefox on Linux')

  await page.getByRole('link', { name: 'Connected browsers' }).click()
  await expect(page.getByRole('heading', { level: 2, name: 'Connected browsers' })).toBeVisible()
  await expect(page.getByText('Firefox on Linux')).toBeVisible()
  await page.getByRole('button', { name: 'Disconnect Firefox on Linux' }).click()
  await page.getByRole('dialog', { name: 'Disconnect this browser?' }).getByRole('button', { name: 'Disconnect' }).click()
  await expect(page.getByText('No browsers are connected.')).toBeVisible()
  expect((await request.get('/api/v2/me/', extension)).status()).toBe(401)
})

test('a signed-out visitor signs in first and comes back to the request', async ({ page }) => {
  const email = uniqueEmail('connect-signin')
  await signUpThroughApi(page, email)
  await page.context().clearCookies()
  const { challenge } = pkce()
  await playExtension(page, challenge)

  await page.goto(connectUrl(challenge, 'Chrome on Windows'))
  await expect(page.getByRole('heading', heading('Sign in'))).toBeVisible()
  await page.getByRole('textbox', { name: 'Email' }).fill(email)
  await page.getByLabel('Password', { exact: true }).fill(PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).last().click()

  await expect(page.getByRole('heading', heading('Connect this browser?'))).toBeVisible()
  await expect(page.locator('dd')).toHaveText(['Chrome on Windows', email])
})

test('nothing can be approved unless the extension in this browser asked', async ({ page }) => {
  await signUpThroughApi(page, uniqueEmail('connect-none'))
  const { challenge } = pkce()

  // No extension here: someone followed a link, or the extension isn't installed.
  await page.goto(connectUrl(challenge))
  await expect(page.getByRole('heading', heading('Open this page from the extension'))).toBeVisible()
  await expect(page.getByRole('button', { name: 'Connect', exact: true })).toHaveCount(0)

  // An extension is here, but it didn't start this request: a link someone sent.
  await playExtension(page, challenge, false)
  await page.goto(connectUrl(challenge))
  await expect(page.getByRole('heading', heading("This request didn't come from your extension"))).toBeVisible()
  await expect(page.getByRole('button', { name: 'Connect', exact: true })).toHaveCount(0)
})

test('the extension reports a failure and the user tries again', async ({ page, request }) => {
  await signUpThroughApi(page, uniqueEmail('connect-retry'))
  const { verifier, challenge } = pkce()
  await playExtension(page, challenge)
  await page.goto(connectUrl(challenge))
  await page.getByRole('button', { name: 'Connect', exact: true }).click()
  const first = await handedCode(page)

  await extensionSays(page, challenge, 'failed', "Couldn't reach listlinkedin.")
  await expect(page.getByRole('heading', heading("This browser wasn't connected"))).toBeVisible()
  await expect(page.getByText("Couldn't reach listlinkedin.")).toBeVisible()

  await page.getByRole('button', { name: 'Try again' }).click()
  await expect.poll(() => handedCode(page)).not.toBe(first) // a new code each time
  const exchange = await request.post('/api/v2/browsers/connect/', {
    data: { code: await handedCode(page), verifier },
  })
  expect(exchange.status(), await exchange.text()).toBe(201)
  await extensionSays(page, challenge, 'connected')
  await expect(page.getByRole('heading', heading('This browser is connected'))).toBeVisible()
})

test('a second browser shows up next to the first', async ({ page, request }) => {
  await signUpThroughApi(page, uniqueEmail('connect-two'))
  await connectBrowser(page, request, 'Firefox on Linux')
  await connectBrowser(page, request, 'Chrome on Windows')

  await page.goto('/account')
  const names = page.locator('.ll-account-browsers li .text-body-large')
  await expect(names).toHaveText(['Chrome on Windows', 'Firefox on Linux']) // newest first
})
