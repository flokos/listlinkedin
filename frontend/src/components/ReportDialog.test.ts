import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { createVuetify } from 'vuetify'

import { ApiError } from '../api'
import ReportDialog from './ReportDialog.vue'

const vuetify = createVuetify()

// The dialog's shell needs browser APIs jsdom lacks; its content is what is under test.
const VDialog = defineComponent(
  (_, { slots }) =>
    () =>
      h('div', slots.default?.()),
)

async function mountDialog(send = vi.fn().mockResolvedValue(null)) {
  const wrapper = mount(ReportDialog, {
    props: { modelValue: true, kind: 'list', title: 'Dev tools', send },
    global: { plugins: [vuetify], stubs: { VDialog } },
  })
  await flushPromises()
  const choose = async (index: number) => {
    await wrapper.findAll('input[type="radio"]')[index]!.setValue(true)
  }
  const submit = async () => {
    await wrapper.find('form').trigger('submit')
    await flushPromises()
  }
  return { wrapper, send, choose, submit }
}

describe('ReportDialog', () => {
  it('needs a reason, then sends it with the trimmed details', async () => {
    const { wrapper, send, choose, submit } = await mountDialog()
    await submit()
    expect(send).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Choose what is wrong.')

    await choose(0)
    await wrapper.find('textarea').setValue('  Asks for my bank password  ')
    await submit()
    expect(send).toHaveBeenCalledWith({
      reason: 'phishing',
      details: 'Asks for my bank password',
    })
    expect(wrapper.emitted('sent')).toHaveLength(1)
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
    wrapper.unmount()
  })

  it('asks what is wrong when the reason is "something else"', async () => {
    const { wrapper, send, choose, submit } = await mountDialog()
    await choose(3)
    expect(wrapper.text()).toContain('What is wrong?')
    await submit()
    expect(send).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Tell us what is wrong.')
    wrapper.unmount()
  })

  it("shows why a report couldn't be sent, and stays open", async () => {
    const send = vi
      .fn()
      .mockRejectedValue(
        new ApiError(503, { detail: "Your report couldn't be sent. Please try again later." }),
      )
    const { wrapper, choose, submit } = await mountDialog(send)
    await choose(1)
    await submit()
    expect(wrapper.text()).toContain("Your report couldn't be sent. Please try again later.")
    expect(wrapper.emitted('sent')).toBeUndefined()
    wrapper.unmount()
  })
})
