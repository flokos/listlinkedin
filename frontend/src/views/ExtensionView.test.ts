import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createVuetify } from 'vuetify'

import ExtensionView from './ExtensionView.vue'

async function open() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/extension', name: 'extension', component: ExtensionView },
      { path: '/account', name: 'account', component: { render: () => null } },
      { path: '/about', name: 'about', component: { render: () => null } },
    ],
  })
  await router.push('/extension')
  await router.isReady()
  return mount(ExtensionView, { global: { plugins: [createVuetify(), router] } })
}

describe('ExtensionView', () => {
  it('links to the builds of the latest release, under names that stay the same', async () => {
    const wrapper = await open()
    const href = (text: string) =>
      wrapper
        .findAll('a')
        .find((link) => link.text().includes(text))!
        .attributes('href')

    expect(wrapper.find('h1').text()).toBe('Browser extension')
    // .github/workflows/extension-release.yml attaches exactly these names.
    expect(href('Download for Chrome')).toBe(
      'https://github.com/flokos/listlinkedin/releases/latest/download/listlinkedin-chrome.zip',
    )
    expect(href('Download for Firefox')).toBe(
      'https://github.com/flokos/listlinkedin/releases/latest/download/listlinkedin-firefox.xpi',
    )
    expect(href('see the latest release')).toBe(
      'https://github.com/flokos/listlinkedin/releases/latest',
    )
  })

  it('opens the other site in a new tab without telling it where the visitor came from', async () => {
    const wrapper = await open()
    const outside = wrapper
      .findAll('a')
      .filter((link) => link.attributes('href')?.startsWith('https://'))
    expect(outside).toHaveLength(4)
    for (const link of outside) expect(link.attributes('rel')).toBe('noopener noreferrer')
  })

  it('leads to the account page and to the privacy page', async () => {
    const wrapper = await open()
    const inside = wrapper.findAll('a').map((link) => link.attributes('href'))
    expect(inside).toContain('/account')
    expect(inside).toContain('/about')
  })
})
