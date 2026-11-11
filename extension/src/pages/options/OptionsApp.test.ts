import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { getConnection, saveConnection } from '../../lib/storage'
import { ADA, browser, json } from '../../test/fakeBrowser'
import { site } from '../../test/site'
import OptionsApp from './OptionsApp.vue'

describe('the options page', () => {
  it('shows the account and disconnects after asking once more', async () => {
    await saveConnection(ADA)
    const { calls } = site({ [`DELETE /api/v2/me/browsers/${ADA.id}/`]: () => json(null, 204) })
    const wrapper = mount(OptionsApp)
    await flushPromises()
    const button = (text: string) => wrapper.findAll('button').find((b) => b.text() === text)

    expect(wrapper.text()).toContain('ada@example.com')
    expect(wrapper.text()).toContain('Firefox on Linux')
    expect(wrapper.find('a').attributes('href')).toBe('https://lists.example.test/account')

    await button('Disconnect…')!.trigger('click')
    expect(calls).toEqual([]) // nothing yet: the user confirms first
    await button('Cancel')!.trigger('click')
    await button('Disconnect…')!.trigger('click')
    await button('Disconnect this browser')!.trigger('click')
    await flushPromises()

    expect(calls).toEqual([`DELETE /api/v2/me/browsers/${ADA.id}/`])
    expect(await getConnection()).toBeNull()
    expect(wrapper.text()).toContain('Connect this browser')
  })

  it('lists the shortcuts as the browser has them, and opens where they are changed', async () => {
    browser().commands.getAll.mockResolvedValue([
      { name: '_execute_action', description: '', shortcut: 'Alt+Shift+L' },
      {
        name: 'save-page',
        description: 'Save this page to the list you saved to last',
        shortcut: '',
      },
    ])
    const wrapper = mount(OptionsApp)
    await flushPromises()

    expect(wrapper.findAll('dt').map((term) => term.text())).toEqual([
      'Open listlinkedin for this page', // Chrome gives the popup's shortcut no description
      'Save this page to the list you saved to last',
    ])
    expect(wrapper.findAll('dd').map((value) => value.text())).toEqual(['Alt+Shift+L', 'Not set'])

    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Change shortcuts')!
      .trigger('click')
    expect(browser().tabs.create).toHaveBeenCalledWith({ url: 'chrome://extensions/shortcuts' })
  })

  it('offers to connect when no account is connected', async () => {
    const wrapper = mount(OptionsApp)
    await flushPromises()
    expect(wrapper.text()).toContain('Connect this browser')
    expect(wrapper.text()).toContain('talks to lists.example.test and to no other site')
  })
})
