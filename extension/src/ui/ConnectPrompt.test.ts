import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { browser } from '../test/fakeBrowser'

const connect = vi.hoisted(() => ({ startConnect: vi.fn() }))
vi.mock('../lib/connect', () => connect)

import ConnectPrompt from './ConnectPrompt.vue'

async function show(props = {}) {
  const wrapper = mount(ConnectPrompt, { props })
  await flushPromises()
  const button = (text: string) => wrapper.findAll('button').find((b) => b.text() === text)
  return { wrapper, button }
}

beforeEach(() => {
  connect.startConnect.mockReset().mockResolvedValue(undefined)
})

describe('ConnectPrompt', () => {
  it('starts connecting on the site', async () => {
    const { wrapper, button } = await show()

    await button('Connect this browser')!.trigger('click')
    await flushPromises()

    expect(connect.startConnect).toHaveBeenCalledOnce()
    expect(wrapper.emitted('started')).toHaveLength(1)
    expect(wrapper.text()).toContain('Your password is never typed into the extension')
  })

  it('asks for access to the site first when the browser has not granted it', async () => {
    browser().permissions.contains.mockResolvedValue(false)
    const { wrapper, button } = await show()
    expect(button('Connect this browser')).toBeUndefined()
    expect(wrapper.text()).toContain('lists.example.test')

    browser().permissions.request.mockResolvedValue(false)
    await button('Allow access')!.trigger('click')
    await flushPromises()
    expect(browser().permissions.request).toHaveBeenCalledWith({
      origins: ['https://lists.example.test/*'],
    })
    expect(wrapper.find('[role="alert"]').text()).toContain("can't save anything")

    browser().permissions.request.mockResolvedValue(true)
    await button('Allow access')!.trigger('click')
    await flushPromises()
    expect(button('Connect this browser')).toBeDefined()
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('says so when the connection had ended, and when the page could not be opened', async () => {
    connect.startConnect.mockRejectedValue(new Error('No window'))
    const { wrapper, button } = await show({ ended: true })
    expect(wrapper.find('[role="status"]').text()).toContain('was disconnected')

    await button('Connect this browser')!.trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').text()).toContain("Couldn't open listlinkedin")
    expect(wrapper.emitted('started')).toBeUndefined()
  })
})
