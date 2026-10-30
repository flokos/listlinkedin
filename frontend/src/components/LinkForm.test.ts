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
      description: null,
    })
  })

  it('submits a trimmed description and refuses one over the limit', async () => {
    const { wrapper, url, submit } = mountForm()
    const description = wrapper.find('textarea')
    await url.setValue('https://example.com/')
    await description.setValue('x'.repeat(1001))
    await wrapper.find('form').trigger('submit')
    await vi.waitFor(() =>
      expect(wrapper.text()).toContain('Descriptions can be at most 1000 characters.'),
    )
    expect(submit).not.toHaveBeenCalled()
    await description.setValue('  Worth reading.  ')
    await wrapper.find('form').trigger('submit')
    await vi.waitFor(() => expect(submit).toHaveBeenCalled())
    expect(submit.mock.calls[0]![0]).toMatchObject({ description: 'Worth reading.' })
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

  it("offers the page's title and description without filling them in", async () => {
    const submit = vi.fn().mockResolvedValue(undefined)
    const wrapper = mount(LinkForm, {
      props: {
        mode: 'edit',
        initial: { url: 'https://example.com/', title: 'Mine', description: null },
        suggestions: { title: 'Page title', description: 'Page description' },
        submit,
      },
      global: { plugins: [vuetify] },
    })
    const [, title] = wrapper.findAll('input')
    expect(title!.element.value).toBe('Mine') // the user's value stays
    expect(wrapper.text()).toContain("The page's title: “Page title”")

    await wrapper.find('button[aria-label="Use the page\'s title, Page title"]').trigger('click')
    expect(title!.element.value).toBe('Page title')
    expect(wrapper.text()).not.toContain("The page's title") // used: nothing left to offer
    await wrapper.find('button[aria-label="Use the page\'s description"]').trigger('click')
    await wrapper.find('form').trigger('submit')
    await vi.waitFor(() =>
      expect(submit).toHaveBeenCalledWith({
        destination_url: 'https://example.com/',
        title: 'Page title',
        description: 'Page description',
      }),
    )
  })
})
