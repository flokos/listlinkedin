import { defineConfig, devices } from '@playwright/test'

// Runs inside the e2e container on the compose network of the production stack (run.sh):
// real nginx → production Vue build → Gunicorn, over HTTPS with a throwaway certificate.
const desktop = { viewport: { width: 1280, height: 900 } }

// Specs about app logic (mocked responses, the 100-link limit) gain nothing from other
// engines. axe inspects the DOM and computed styles, so its results don't depend on the
// engine either, and it is several times slower in Gecko and WebKit: accessibility runs on
// Chromium, desktop and mobile layouts.
const chromiumOnly = /(states|limits)\.spec\.ts/
const notOnGeckoOrWebKit = [chromiumOnly, /a11y\.spec\.ts/]

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.E2E_RETRIES ? Number(process.env.E2E_RETRIES) : 0,
  workers: process.env.E2E_WORKERS ? Number(process.env.E2E_WORKERS) : 4,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: [['list'], ['html', { outputFolder: 'report', open: 'never' }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'https://go.example.test',
    ignoreHTTPSErrors: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    locale: 'en-US',
    timezoneId: 'UTC',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'], ...desktop } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'], ...desktop }, testIgnore: notOnGeckoOrWebKit },
    { name: 'webkit', use: { ...devices['Desktop Safari'], ...desktop }, testIgnore: notOnGeckoOrWebKit },
    { name: 'mobile-safari', use: { ...devices['iPhone 15'] }, testIgnore: notOnGeckoOrWebKit },
    { name: 'mobile-chrome', use: { ...devices['Pixel 7'] }, testIgnore: chromiumOnly },
  ],
})
