// Accounts end to end: sign-up, email verification, sign-in, password reset and the account
// page, with real emails caught by Mailpit. Runs in every browser: session cookies, CSRF and
// SameSite behaviour are exactly where engines differ.
import type { Page } from '@playwright/test'

import { emailTo, expect, linkIn, PASSWORD, signUpThroughApi, test, uniqueEmail } from './fixtures'

const main = (page: Page) => page.getByRole('main')

test('sign up, verify the email address, sign out and sign back in', async ({ page, request }) => {
  const email = uniqueEmail('signup')
  await page.goto('/signin')
  await main(page).getByRole('link', { name: 'Create an account' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Create your account' })).toBeVisible()

  await page.getByRole('textbox', { name: 'Your name (optional)' }).fill('Ada')
  await page.getByRole('textbox', { name: 'Email' }).fill(email)
  await page.getByLabel('Password', { exact: true }).fill(PASSWORD)
  await page.getByRole('button', { name: 'Create account' }).click()

  await expect(page.getByRole('heading', { level: 1, name: 'Your account' })).toBeVisible()
  await expect(page.getByRole('textbox', { name: 'Your name' })).toHaveValue('Ada')
  await expect(page.getByText('Not verified')).toBeVisible()

  // The emailed link carries its key in the fragment; the page removes it at once.
  await page.goto(linkIn(await emailTo(request, email, /confirm/i), '/verify-email'))
  await expect(page.getByRole('heading', { level: 1, name: 'Your email is verified' })).toBeVisible()
  expect(new URL(page.url()).hash).toBe('')
  await page.getByRole('link', { name: 'Go to your account' }).click()
  await expect(page.getByText('Verified', { exact: true })).toBeVisible()

  await main(page).getByRole('button', { name: 'Sign out' }).click()
  await expect(page.getByRole('heading', { level: 1, name: /Collect links/ })).toBeVisible()

  // Pages that need an account send you to sign in, then back.
  await page.goto('/account')
  await expect(page).toHaveURL(/\/signin\?next=(\/|%2F)account$/)
  await page.getByRole('textbox', { name: 'Email' }).fill(email)
  await page.getByLabel('Password', { exact: true }).fill('not-the-password')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByText(/email address and\/or password you specified are not correct/)).toBeVisible()

  await page.getByLabel('Password', { exact: true }).fill(PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Your account' })).toBeVisible()
  await expect(page).toHaveURL(/\/account$/)
})

test('reset a forgotten password from the emailed link', async ({ page, request }) => {
  const email = uniqueEmail('reset')
  await signUpThroughApi(page, email)
  await page.context().clearCookies() // signed out

  await page.goto('/signin')
  await page.getByRole('link', { name: 'Forgot your password?' }).click()
  // Wait for the new page: the sign-in page has an "Email" field too, and typing into it
  // while the reset page loads loses the address (a CI flake, traced 2026-10-29).
  await expect(page.getByRole('heading', { level: 1, name: 'Reset your password' })).toBeVisible()
  await page.getByRole('textbox', { name: 'Email' }).fill(email)
  await page.getByRole('button', { name: 'Send reset link' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Check your inbox' })).toBeVisible()

  const link = linkIn(await emailTo(request, email, /password reset/i), '/reset-password')
  await page.goto(link)
  await expect(page.getByRole('heading', { level: 1, name: 'Choose a new password' })).toBeVisible()
  expect(new URL(page.url()).hash).toBe('')
  await page.getByLabel('New password', { exact: true }).fill(`${PASSWORD}-new`)
  await page.getByRole('button', { name: 'Set new password' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Your password was changed' })).toBeVisible()

  await main(page).getByRole('link', { name: 'Sign in' }).click()
  await page.getByRole('textbox', { name: 'Email' }).fill(email)
  await page.getByLabel('Password', { exact: true }).fill(`${PASSWORD}-new`)
  await page.getByRole('button', { name: 'Sign in' }).click()
  // Wait for the redirect home to finish, not just for the header: Firefox cancels a new
  // page load if the old page is still updating its history.
  await expect(page.getByRole('heading', { level: 1, name: /Collect links/ })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Account menu' })).toBeVisible()

  // A reset link works once.
  await page.goto(link)
  await expect(
    page.getByRole('heading', { level: 1, name: 'This link has expired or was already used' }),
  ).toBeVisible()
})

test('change your name and password on the account page', async ({ page }) => {
  await signUpThroughApi(page, uniqueEmail('account'))
  await page.goto('/account')

  await page.getByRole('textbox', { name: 'Your name' }).fill('Grace')
  await page.getByRole('button', { name: 'Save name' }).click()
  await expect(page.getByText('Name saved')).toBeVisible()
  await page.reload()
  await expect(page.getByRole('textbox', { name: 'Your name' })).toHaveValue('Grace')

  await page.getByLabel('Current password', { exact: true }).fill('wrong-password')
  await page.getByLabel('New password', { exact: true }).fill(`${PASSWORD}-2`)
  await page.getByRole('button', { name: 'Change password' }).click()
  await expect(page.getByText('Please type your current password.')).toBeVisible()

  await page.getByLabel('Current password', { exact: true }).fill(PASSWORD)
  await page.getByRole('button', { name: 'Change password' }).click()
  await expect(page.getByText('Password changed')).toBeVisible()
})

test('signing in only ever continues to a page on this site', async ({ page, baseURL }) => {
  const email = uniqueEmail('next')
  await signUpThroughApi(page, email)
  await page.context().clearCookies()

  await page.goto('/signin?next=//evil.example/steal')
  await page.getByRole('textbox', { name: 'Email' }).fill(email)
  await page.getByLabel('Password', { exact: true }).fill(PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { level: 1, name: /Collect links/ })).toBeVisible()
  expect(new URL(page.url()).origin).toBe(new URL(baseURL!).origin)
  expect(new URL(page.url()).pathname).toBe('/')

  // Signed in, the sign-in page itself moves straight on to `next`.
  await page.goto('/signin?next=/about')
  await expect(page.getByRole('heading', { level: 1, name: 'About & privacy' })).toBeVisible()
})
