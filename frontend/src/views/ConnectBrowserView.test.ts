import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createVuetify } from 'vuetify'

import { ApiError } from '../api'

const api = vi.hoisted(() => ({ approveBrowser: vi.fn() }))
vi.mock('../api', async (original) => ({
  ...(await original<typeof import('../api')>()),
  approveBrowser: api.approveBrowser,
}))
const bridge = vi.hoisted(() => ({ findExtension: vi.fn(), sendCode: vi.fn() }))
vi.mock('../utils/extensionBridge', () => bridge)

import ConnectBrowserView from './ConnectBrowserView.vue'

const vuetify = createVuetify()
const CHALLENGE = 'c'.repeat(43)
const page = { render: () => null }

async function open(query = `?challenge=${CHALLENGE}&name=Firefox%20on%20Linux`) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/connect-browser', name: 'connect-browser', component: ConnectBrowserView },
      { path: '/', name: 'home', component: page },
      { path: '/lists', name: 'saved-lists', component: page },
      { path: '/account', name: 'account', component: page },
      { path: '/signin', name: 'signin', component: page },
    ],
  })
  await router.push(`/connect-browser${query}`)
  const wrapper = mount(ConnectBrowserView, { global: { plugins: [vuetify, router] } })
  await flushPromises()
  const button = (text: string) => wrapper.findAll('button').find((b) => b.text() === text)
  return { wrapper, router, button }
}

beforeEach(() => {
  vi.clearAllMocks()
  bridge.findExtension.mockResolvedValue(true)
  bridge.sendCode.mockResolvedValue(undefined)
  api.approveBrowser.mockResolvedValue({ code: 'one-time-code', expires_in: 120 })
})

describe('ConnectBrowserView', () => {
  it('asks before connecting, then hands the code to the extension', async () => {
    const { wrapper, button } = await open()
    expect(wrapper.find('h1').text()).toBe('Connect this browser?')
    expect(wrapper.text()).toContain('Firefox on Linux')
    expect(api.approveBrowser).not.toHaveBeenCalled()

    await button('Connect')!.trigger('click')
    await flushPromises()

    expect(api.approveBrowser).toHaveBeenCalledWith(CHALLENGE, 'Firefox on Linux')
    expect(bridge.sendCode).toHaveBeenCalledWith(CHALLENGE, 'one-time-code')
    expect(wrapper.find('h1').text()).toBe('This browser is connected')
    expect(wrapper.text()).not.toContain('one-time-code')
  })

  it('offers nothing to approve when the page was not opened by the extension', async () => {
    for (const query of ['', '?challenge=short', `?challenge=${CHALLENGE}`]) {
      bridge.findExtension.mockResolvedValue(null)
      const { wrapper, button } = await open(query)
      expect(wrapper.find('h1').text()).toBe('Open this page from the extension')
      expect(button('Connect')).toBeUndefined()
    }
    expect(bridge.findExtension).toHaveBeenCalledTimes(1) // only with a well-formed challenge
  })

  it("refuses a request this browser's extension didn't start", async () => {
    bridge.findExtension.mockResolvedValue(false)
    const { wrapper, button } = await open()
    expect(wrapper.find('h1').text()).toBe("This request didn't come from your extension")
    expect(button('Connect')).toBeUndefined()
    expect(api.approveBrowser).not.toHaveBeenCalled()
  })

  it('shows a long or odd name as one line of plain text', async () => {
    const { wrapper } = await open(
      `?challenge=${CHALLENGE}&name=${encodeURIComponent(` <b>Fire\nfox</b>${'x'.repeat(200)}`)}`,
    )
    expect(wrapper.find('dd').text()).toBe(`<b>Fire fox</b>${'x'.repeat(200)}`.slice(0, 80))
    expect(wrapper.find('dd b').exists()).toBe(false)
  })

  it('says why when ten browsers are connected already', async () => {
    api.approveBrowser.mockRejectedValue(
      new ApiError(409, {
        detail: 'You can connect at most 10 browsers.',
        code: 'too_many_browsers',
      }),
    )
    const { wrapper, button } = await open()
    await button('Connect')!.trigger('click')
    await flushPromises()

    expect(wrapper.find('h1').text()).toBe("This browser wasn't connected")
    expect(wrapper.text()).toContain('You can connect at most 10 browsers.')
    expect(wrapper.text()).toContain('Connected browsers')
    expect(button('Try again')).toBeUndefined()
  })

  it('lets the user try again when the extension could not finish', async () => {
    bridge.sendCode.mockRejectedValueOnce(new Error('The code had expired.'))
    const { wrapper, button } = await open()
    await button('Connect')!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('The code had expired.')

    await button('Try again')!.trigger('click')
    await flushPromises()
    expect(api.approveBrowser).toHaveBeenCalledTimes(2) // a new code each time
    expect(wrapper.find('h1').text()).toBe('This browser is connected')
  })

  it('sends a visitor who was signed out meanwhile to sign in and back', async () => {
    api.approveBrowser.mockRejectedValue(new ApiError(401, { detail: 'Sign in.' }))
    const { router, button } = await open()
    await button('Connect')!.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('signin')
    expect(router.currentRoute.value.query.next).toBe(
      `/connect-browser?challenge=${CHALLENGE}&name=Firefox%20on%20Linux`,
    )
  })
})
