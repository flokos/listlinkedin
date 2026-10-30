// Reporting (roadmap 9.0; docs/v2/13-SECURITY.md#moderation): a visitor who isn't signed in
// reports a public list or group, and the operator is emailed (Mailpit stands in for the
// moderation mailbox). The owner has nothing to report.
import { apiAs, createAccountList, emailTo, expect, otherDevice, signUpVerified, test, uniqueEmail } from './fixtures'

const MODERATION = 'moderation@example.test'

test('a visitor reports a public list and the operator is emailed', async ({ page, browser, baseURL }) => {
  test.slow() // two devices and an email
  const title = `Report me ${Date.now().toString(36)}`
  await signUpVerified(page, uniqueEmail('reported'), 'Owner')
  const { code } = await createAccountList(page, title)
  await apiAs(page, 'PATCH', `/api/v2/lists/${code}/`, { visibility: 'public' }, 200)

  await page.goto(`/l/${code}`)
  await page.getByRole('button', { name: 'List options' }).click()
  await expect(page.getByRole('menuitem', { name: 'Settings' })).toBeVisible()
  await expect(page.getByRole('menuitem', { name: 'Report…' })).toBeHidden()
  await page.keyboard.press('Escape')

  const visitor = await otherDevice(browser, baseURL)
  await visitor.page.goto(`/l/${code}`)
  await visitor.page.getByRole('button', { name: 'List options' }).click()
  await visitor.page.getByRole('menuitem', { name: 'Report…' }).click()
  const dialog = visitor.page.getByRole('dialog', { name: 'Report this list' })
  await dialog.getByRole('button', { name: 'Send report' }).click()
  await expect(dialog.getByText('Choose what is wrong.')).toBeVisible()
  await dialog.getByRole('radio', { name: /^Phishing or malware/ }).check()
  await dialog.getByRole('textbox', { name: 'Details (optional)' }).fill('It asks for bank passwords.')
  await dialog.getByRole('button', { name: 'Send report' }).click()
  await expect(visitor.page.getByText("Thanks. We've received your report.")).toBeVisible()
  await expect(dialog).toBeHidden()

  const mail = await emailTo(visitor.page.request, MODERATION, new RegExp(title))
  expect(mail).toContain('Reason: Phishing or malware')
  expect(mail).toContain('Details: It asks for bank passwords.')
  expect(mail).toContain(`Code: ${code}`)
  expect(mail).toContain("Reported by: someone who wasn't signed in")
  await visitor.context.close()
})

test('a visitor reports a public group', async ({ page, browser, baseURL }) => {
  test.slow()
  const title = `Reported group ${Date.now().toString(36)}`
  await signUpVerified(page, uniqueEmail('reported-group'), 'Group owner')
  const group = await apiAs(page, 'POST', '/api/v2/groups/', { title })
  await apiAs(page, 'PATCH', `/api/v2/groups/${group.code}/`, { visibility: 'public' }, 200)

  const visitor = await otherDevice(browser, baseURL)
  await visitor.page.goto(new URL(group.url).pathname)
  await visitor.page.getByRole('button', { name: `More actions for the group ${title}` }).click()
  await visitor.page.getByRole('menuitem', { name: 'Report…' }).click()
  const dialog = visitor.page.getByRole('dialog', { name: 'Report this group' })
  await dialog.getByRole('radio', { name: /^Something else/ }).check()
  await dialog.getByRole('textbox', { name: 'What is wrong?' }).fill('Impersonates our school.')
  await dialog.getByRole('button', { name: 'Send report' }).click()
  await expect(visitor.page.getByText("Thanks. We've received your report.")).toBeVisible()

  const mail = await emailTo(visitor.page.request, MODERATION, new RegExp(title))
  expect(mail).toContain('Reason: Something else')
  expect(mail).toContain('Details: Impersonates our school.')
  await visitor.context.close()
})
