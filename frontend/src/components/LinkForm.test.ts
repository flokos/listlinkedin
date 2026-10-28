import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { createVuetify } from 'vuetify'

import { ApiError } from '../api'
import LinkForm from './LinkForm.vue'

const vuetify = createVuetify()

function mountForm(submit = vi.fn().mockResolvedValue(undefined)) {
  const wrapper = mount(LinkForm, {
    props: { mode: 'add', submit },
    global: { plugins: [vuetify] },
  })
  const [url, title] = wrapper.findAll('input')
  return { wrapper, url: url!, title: title!, submit }
}

describe('LinkForm', () => {
  it('adds https:// and submits a trimmed title', async () => {
    const { wrapper, url, title, submit } = mountForm()
    await url.setValue('example.com/post')
    await title.setValue('  A post  ')
    await wrapper.find('form').trigger('submit')
    await vi.waitFor(() => expect(submit).toHaveBeenCalled())
    expect(submit).toHaveBeenCalledWith({
      destination_url: 'https://example.com/post',
      title: 'A post',
    })
  })

  it('blocks invalid links before calling the server', async () => {
    const { wrapper, url, submit } = mountForm()
    await url.setValue('ftp://files.example.com')
    await wrapper.find('form').trigger('submit')
    await vi.waitFor(() =>
      expect(wrapper.text()).toContain('Only http and https links are allowed.'),
    )
    expect(submit).not.toHaveBeenCalled()
  })

  it('shows server field errors under the matching field', async () => {
    const submit = vi
      .fn()
      .mockRejectedValue(
        new ApiError(400, { destination_url: ['This URL is already in the list.'] }),
      )
    const { wrapper, url } = mountForm(submit)
    await url.setValue('https://example.com/')
    await wrapper.find('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper.text()).toContain('This URL is already in the list.'))
  })
})
