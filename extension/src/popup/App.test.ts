import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { problem } from '../lib/feedback'
import { forgetAccount, saveConnection } from '../lib/storage'
import { ADA, browser } from '../test/fakeBrowser'
import App from './App.vue'

const SavePanel = {
  name: 'SavePanel',
  template: '<div class="save-panel" />',
  emits: ['disconnected'],
}

const BrowsePanel = {
  name: 'BrowsePanel',
  template: '<div class="browse-panel" />',
  emits: ['disconnected'],
}

async function open() {
  const wrapper = mount(App, { global: { stubs: { SavePanel, BrowsePanel } } })
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

  it('switches between saving this page and the lists, keeping what was typed', async () => {
    await saveConnection(ADA)
    const wrapper = await open()
    const view = (name: string) => wrapper.findAll('button').find((b) => b.text() === name)!
    const shown = (selector: string) =>
      (wrapper.find(selector).element as HTMLElement).style.display !== 'none'

    expect(view('Save this page').attributes('aria-pressed')).toBe('true')
    expect(wrapper.find('.browse-panel').exists()).toBe(false) // not loaded before it is asked for

    await view('My lists').trigger('click')
    expect(view('My lists').attributes('aria-pressed')).toBe('true')
    expect(shown('.browse-panel')).toBe(true)
    expect(wrapper.find('.save-panel').exists()).toBe(true) // hidden, not thrown away
    expect(shown('.save-panel')).toBe(false)

    await view('Save this page').trigger('click')
    expect(shown('.save-panel')).toBe(true)
    expect(shown('.browse-panel')).toBe(false)
  })

  it('says how the last right-click or shortcut went, once, and clears the mark', async () => {
    await saveConnection(ADA)
    await problem("example.com wasn't saved to “Reading”. This URL is already in the list.", 'info')
    expect(browser().action.badge.text).toBe('!')

    const wrapper = await open()
    expect(wrapper.find('[role="status"]').text()).toContain('This URL is already in the list.')
    expect(browser().action.badge.text).toBe('')

    expect((await open()).find('[role="status"]').exists()).toBe(false)
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
