import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createVuetify } from 'vuetify'

import { EXTENSION_VERSION } from '../utils/extensionDownloads'
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
  it("links to Mozilla's add-on page and to the files of the extension's own release", async () => {
    const wrapper = await open()
    const href = (text: string) =>
      wrapper
        .findAll('a')
        .find((link) => link.text().includes(text))!
        .attributes('href')

    expect(wrapper.find('h1').text()).toBe('Browser extension')
    // .github/workflows/extension-release.yml publishes exactly these names under this tag.
    const version = EXTENSION_VERSION
    const files = `https://github.com/flokos/listlinkedin/releases/download/extension-v${version}`
    expect(href('Download for Chrome')).toBe(`${files}/listlinkedin-${version}-chrome.zip`)
    // The address .github/workflows/extension-release.yml submits the add-on under (the
    // slug in extension/amo-metadata.json).
    expect(href('Get it for Firefox')).toBe(
      'https://addons.mozilla.org/firefox/addon/listlinkedin/',
    )
    expect(href("See this version's files")).toBe(
      `https://github.com/flokos/listlinkedin/releases/tag/extension-v${version}`,
    )
    expect(wrapper.text()).toContain(`This is version ${version}.`)
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
