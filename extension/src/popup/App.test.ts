import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { forgetAccount, saveConnection } from '../lib/storage'
import { ADA, browser } from '../test/fakeBrowser'
import App from './App.vue'

const SavePanel = {
  name: 'SavePanel',
  template: '<div class="save-panel" />',
  emits: ['disconnected'],
}

async function open() {
  const wrapper = mount(App, { global: { stubs: { SavePanel } } })
  await flushPromises()
  return wrapper
}

describe('the popup', () => {
  it('offers to connect until a browser is connected, then to save', async () => {
    const wrapper = await open()
    expect(wrapper.text()).toContain('Connect this browser')
    expect(wrapper.find('.save-panel').exists()).toBe(false)

    await saveConnection(ADA) // connected in another tab, on the site
    await flushPromises()
    expect(wrapper.find('.save-panel').exists()).toBe(true)
    expect(wrapper.text()).toContain('ada@example.com')

    expect(wrapper.find('[role="status"]').exists()).toBe(false) // nothing had ended
  })

  it('says so when the connection ends while it is open', async () => {
    await saveConnection(ADA)
    const wrapper = await open()

    // The site answered 401: the account is forgotten (src/lib/account.ts), which the popup
    // hears from storage before the failed request reaches the panel.
    await forgetAccount()
    await flushPromises()

    expect(wrapper.find('[role="status"]').text()).toContain('was disconnected')
    expect(wrapper.find('.save-panel').exists()).toBe(false)
  })

  it('believes the panel when it says the connection is over', async () => {
    await saveConnection(ADA)
    const wrapper = await open()

    wrapper.findComponent(SavePanel).vm.$emit('disconnected')
    await flushPromises()

    expect(wrapper.find('[role="status"]').text()).toContain('was disconnected')
    expect(wrapper.find('.save-panel').exists()).toBe(false)
  })

  it('opens the options page', async () => {
    const wrapper = await open()
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Options')!
      .trigger('click')
    expect(browser().runtime.openOptionsPage).toHaveBeenCalledOnce()
  })
})
