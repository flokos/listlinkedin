import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { createVuetify } from 'vuetify'

const api = vi.hoisted(() => ({ forkList: vi.fn() }))
vi.mock('../api', async (original) => ({ ...(await original<typeof import('../api')>()), ...api }))

import { ApiError, type ListDetail } from '../api'
import CopyListDialog from './CopyListDialog.vue'

const vuetify = createVuetify()
const list = { code: 'SRC', title: 'Dev tools' } as ListDetail

// The dialog's shell needs browser APIs jsdom lacks; its content is what is under test.
const VDialog = defineComponent(
  (_, { slots }) =>
    () =>
      h('div', slots.default?.()),
)

async function mountDialog() {
  const wrapper = mount(CopyListDialog, {
    props: { modelValue: true, list },
    global: { plugins: [vuetify], stubs: { VDialog } },
  })
  await flushPromises()
  const input = () => wrapper.find('input').element as HTMLInputElement
  const submit = async () => {
    await wrapper.find('form').trigger('submit')
    await flushPromises()
  }
  return { wrapper, input, submit }
}

beforeEach(() => api.forkList.mockReset())

describe('CopyListDialog', () => {
  it('suggests "(copy)" and sends the chosen name with an idempotency key', async () => {
    const copy = { code: 'NEW', title: 'Mine' } as ListDetail
    api.forkList.mockResolvedValue(copy)
    const { wrapper, input, submit } = await mountDialog()
    expect(input().value).toBe('Dev tools (copy)')

    input().value = 'Mine'
    input().dispatchEvent(new Event('input'))
    await submit()

    expect(api.forkList).toHaveBeenCalledWith('SRC', { title: 'Mine' }, expect.any(String))
    expect(wrapper.emitted('copied')).toEqual([[copy]])
    wrapper.unmount()
  })

  it('retries with the same key after a failure, and shows why it failed', async () => {
    api.forkList
      .mockRejectedValueOnce(
        new ApiError(403, { detail: "The owner of this list doesn't allow copies." }),
      )
      .mockResolvedValueOnce({ code: 'NEW' })
    const { wrapper, submit } = await mountDialog()

    await submit()
    expect(wrapper.text()).toContain("doesn't allow copies")
    expect(wrapper.emitted('copied')).toBeUndefined()
    await submit()

    const [first, second] = api.forkList.mock.calls.map((call) => call[2])
    expect(second).toBe(first)
    expect(wrapper.emitted('copied')).toHaveLength(1)
    wrapper.unmount()
  })

  it('needs a name', async () => {
    const { wrapper, input, submit } = await mountDialog()
    input().value = '  '
    input().dispatchEvent(new Event('input'))
    await submit()
    expect(api.forkList).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Give the copy a name.')
    wrapper.unmount()
  })
})
