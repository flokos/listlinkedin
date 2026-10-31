// Shared fixtures and helpers. Specs import { test, expect } from here, not from
// @playwright/test, so every test fails on unexpected console errors.
import AxeBuilder from '@axe-core/playwright'
import { type APIRequestContext, type Browser, expect, type Page, test as base } from '@playwright/test'

export interface CreatedList {
  id: string
  public_code: string
  public_url: string
  title: string
  /** The account that owns the list: `openAsOwner` signs in as it. */
  owner: { email: string; password: string }
}

/**
 * API helpers for fast setup (same origin as the app, through nginx). Lists belong to an
 * owner account created for the test, and are unlisted, so visitors can read them by their
 * address. (Until v2.1.0 these were V1 lists managed by an edit link.)
 */
export function apiHelpers(request: APIRequestContext) {
  const owner = { email: uniqueEmail('owner'), password: PASSWORD }
  let signedUp: Promise<void> | undefined
  const csrf = async () => {
    const { cookies } = await request.storageState()
    const named = (name: string) => cookies.find((c) => c.name === name)?.value
    return named('__Host-csrftoken') ?? named('csrftoken') ?? ''
  }
  const headers = async () => ({ 'X-CSRFToken': await csrf(), Origin: ORIGIN })
  const signUp = async () => {
    await request.get('/api/v2/session/') // sets the CSRF cookie
    const response = await request.post('/_allauth/browser/v1/auth/signup', {
      data: owner,
      headers: await headers(),
    })
    expect(response.status(), await response.text()).toBe(200)
  }

  return {
    async createList(title = 'E2E list'): Promise<CreatedList> {
      signedUp ??= signUp()
      await signedUp
      const response = await request.post('/api/v2/lists/', {
        data: { title, visibility: 'unlisted' },
        headers: await headers(),
      })
      expect(response.status(), await response.text()).toBe(201)
      const list = await response.json()
      return { id: list.id, public_code: list.code, public_url: list.url, title, owner }
    },
    async addLink(list: CreatedList, destination_url: string, title?: string) {
      const response = await request.post(`/api/v2/lists/${list.public_code}/links/`, {
        data: { destination_url, title },
        headers: await headers(),
      })
      expect(response.status(), await response.text()).toBe(201)
      return response.json()
    },
    async deleteList(list: CreatedList) {
      const response = await request.delete(`/api/v2/lists/${list.public_code}/`, {
        headers: await headers(),
      })
      expect(response.status()).toBe(204)
    },
  }
}

// Accounts. Mailpit (e2e/compose.e2e.yaml) catches every email the stack sends.
const MAILPIT = 'http://mailpit:8025'
const ORIGIN = new URL(process.env.E2E_BASE_URL ?? 'https://go.example.test').origin
export const PASSWORD = 'correct-horse-battery-staple-42'

/** A fresh address per test, so tests never read each other's mail or collide. */
export function uniqueEmail(label = 'e2e'): string {
  return `${label}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}@example.test`
}

/** Waits for the newest email to `to` whose subject matches, and returns its text body. */
export async function emailTo(request: APIRequestContext, to: string, subject: RegExp): Promise<string> {
  const deadline = Date.now() + 15_000
  while (Date.now() < deadline) {
    const search = await request.get(`${MAILPIT}/api/v1/search`, { params: { query: `to:"${to}"` } })
    const { messages = [] } = (await search.json()) as { messages?: { ID: string; Subject: string }[] }
    const message = messages.find((m) => subject.test(m.Subject))
    if (message) {
      const full = await request.get(`${MAILPIT}/api/v1/message/${message.ID}`)
      return ((await full.json()) as { Text: string }).Text
    }
    await new Promise((resolve) => setTimeout(resolve, 300))
  }
  throw new Error(`No email to ${to} with a subject matching ${subject}`)
}

/** The app link in an email, e.g. `https://…/verify-email#key=…`. */
export function linkIn(text: string, path: string): string {
  const match = text.match(new RegExp(`https://\\S+${path}#key=\\S+`))
  expect(match, text).not.toBeNull()
  return match![0]
}

/** Django's CSRF token from the page's cookies: `__Host-csrftoken` on the production stack
 * the suite runs against (backend/config/settings/production.py), `csrftoken` in development. */
export async function csrfOf(page: Page): Promise<string> {
  const cookies = await page.context().cookies()
  const named = (name: string) => cookies.find((c) => c.name === name)?.value
  return named('__Host-csrftoken') ?? named('csrftoken') ?? ''
}

/**
 * Creates an account through the API and leaves this browser signed in to it: page.request
 * shares the page's cookies. For tests about signed-in pages rather than sign-up itself.
 */
export async function signUpThroughApi(page: Page, email: string, password = PASSWORD) {
  await page.request.get('/api/v2/session/') // sets the CSRF cookie
  const csrf = await csrfOf(page)
  const response = await page.request.post('/_allauth/browser/v1/auth/signup', {
    data: { email, password },
    // Browsers send Origin on these requests themselves; Django checks it over HTTPS.
    headers: { 'X-CSRFToken': csrf, Origin: ORIGIN },
  })
  expect(response.status(), await response.text()).toBe(200)
}

/** Creates an account list through the API as the page's signed-in user. */
export async function createAccountList(page: Page, title: string): Promise<{ code: string }> {
  const csrf = await csrfOf(page)
  const response = await page.request.post('/api/v2/lists/', {
    data: { title },
    headers: { 'X-CSRFToken': csrf, Origin: ORIGIN },
  })
  expect(response.status(), await response.text()).toBe(201)
  return response.json()
}

/** A session-authenticated API write as the page's signed-in user; returns the JSON body. */
export async function apiAs(page: Page, method: 'POST' | 'PATCH', path: string, data: object, status = 201) {
  const csrf = await csrfOf(page)
  const response = await page.request.fetch(path, {
    method,
    data,
    headers: { 'X-CSRFToken': csrf, Origin: ORIGIN },
  })
  expect(response.status(), await response.text()).toBe(status)
  return response.json()
}

/**
 * Like signUpThroughApi, then verifies the address with the key from the emailed link and
 * sets a display name, all through the API (auth.spec tests the verification page itself).
 * Sharing a list needs verified accounts on both sides.
 */
export async function signUpVerified(page: Page, email: string, displayName: string) {
  await signUpThroughApi(page, email)
  const link = linkIn(await emailTo(page.request, email, /confirm/i), '/verify-email')
  const key = decodeURIComponent(new URL(link).hash.replace(/^#key=/, ''))
  const csrf = await csrfOf(page)
  const headers = { 'X-CSRFToken': csrf, Origin: ORIGIN }
  const verified = await page.request.post('/_allauth/browser/v1/auth/email/verify', {
    data: { key },
    headers,
  })
  expect(verified.status(), await verified.text()).toBe(200)
  const named = await page.request.patch('/api/v2/me/', { data: { display_name: displayName }, headers })
  expect(named.status(), await named.text()).toBe(200)
}

/** The title link of a link card (the icon button has a different name). */
export const cardTitle = (page: Page, title: string) =>
  page.getByRole('link', { name: `${title} (opens in a new tab)`, exact: true })

/** All card title links, in display order. */
export const cardTitles = (page: Page) => page.getByRole('link', { name: /\(opens in a new tab\)$/ })

/** Signs this page's browser in as the list's owner and opens the list. */
export async function openAsOwner(page: Page, list: CreatedList) {
  await page.request.get('/api/v2/session/') // sets the CSRF cookie
  const response = await page.request.post('/_allauth/browser/v1/auth/login', {
    data: list.owner,
    headers: { 'X-CSRFToken': await csrfOf(page), Origin: ORIGIN },
  })
  expect(response.status(), await response.text()).toBe(200)
  await page.goto(`/l/${list.public_code}`)
  await expect(page.getByText('Your list', { exact: true })).toBeVisible()
}

/** A second, independent browser (another device): no shared storage. */
export async function otherDevice(browser: Browser, baseURL: string | undefined) {
  const context = await browser.newContext({ baseURL, ignoreHTTPSErrors: true })
  return { context, page: await context.newPage() }
}

/**
 * Fails on WCAG 2.2 A/AA violations found by axe. Waits for running transitions first: a menu
 * or dialog still fading in has semi-transparent text, which axe reports as low contrast.
 */
export async function expectNoA11yViolations(page: Page, include?: string) {
  await page.evaluate(() => {
    const finite = document
      .getAnimations()
      // Paused ones and spinners never finish; a transition takes well under 2 s.
      .filter((a) => a.playState === 'running' && a.effect?.getTiming().iterations !== Infinity)
      .map((a) => a.finished.catch(() => undefined))
    return Promise.race([Promise.all(finite), new Promise((done) => setTimeout(done, 2000))])
  })
  let builder = new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
  if (include) builder = builder.include(include)
  const { violations } = await builder.analyze()
  const summary = violations.map(
    (v) => `${v.id} (${v.impact}): ${v.help}\n  ${v.nodes.map((n) => n.target.join(' ')).join('\n  ')}`,
  )
  expect(summary, summary.join('\n')).toEqual([])
}

// HTTP errors the app handles on purpose show up as console errors in some browsers
// ("Failed to load resource: … 404"). Anything else is a bug.
const EXPECTED_CONSOLE = [/status of (400|401|403|404|410|412|413|428|429|500|502|503)/, /Failed to load resource/]

export const test = base.extend<{ consoleErrors: string[]; api: ReturnType<typeof apiHelpers> }>({
  consoleErrors: [
    async ({ page }, use) => {
      const errors: string[] = []
      page.on('console', (message) => {
        if (message.type() !== 'error') return
        if (EXPECTED_CONSOLE.some((re) => re.test(message.text()))) return
        errors.push(message.text())
      })
      page.on('pageerror', (error) => errors.push(`Uncaught: ${error.message}`))
      await use(errors)
      expect(errors, 'unexpected console errors').toEqual([])
    },
    { auto: true },
  ],
  api: async ({ request }, use) => use(apiHelpers(request)),
})

export { expect }
