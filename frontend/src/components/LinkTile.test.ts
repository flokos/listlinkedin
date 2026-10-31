import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createVuetify } from 'vuetify'

import type { SharedLink } from '../api'
import LinkTile from './LinkTile.vue'

const vuetify = createVuetify()

const link: SharedLink = {
  id: 'l1',
  title: null,
  destination_url: 'https://www.example.com/a',
  short_url: 'https://go.example.test/r/abc',
  created_at: '2026-10-29T10:00:00Z',
  updated_at: '2026-10-29T10:00:00Z',
  description: null,
  icon_url: null,
  display: {
    title: 'Fetched title',
    description: 'From the page',
    icon_url: '/media/icons/ab/ab.webp',
    site_name: 'Example',
  },
}

function mountTile(props: Partial<{ link: SharedLink; canEdit: boolean }> = {}) {
  return mount(LinkTile, {
    props: { link, canEdit: false, ...props },
    global: { plugins: [vuetify] },
  })
}

describe('LinkTile', () => {
  it("shows the server's display values and opens the short link", () => {
    const wrapper = mountTile()
    const anchor = wrapper.find('a.ll-tile__link')
    expect(anchor.text()).toContain('Fetched title')
    expect(anchor.attributes('href')).toBe('https://go.example.test/r/abc')
    expect(wrapper.text()).toContain('Example')
    expect(wrapper.text()).toContain('From the page')
    expect(wrapper.find('img').attributes('src')).toBe('/media/icons/ab/ab.webp')
  })

  it('falls back to the host and the letter avatar without display values', () => {
    const wrapper = mountTile({ link: { ...link, display: undefined } })
    expect(wrapper.find('a.ll-tile__link').text()).toContain('example.com')
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('.ll-domain-avatar').text()).toBe('E')
  })

  it('says when the page details are still being fetched', () => {
    const pending = mountTile({ link: { ...link, metadata_status: 'pending' } })
    expect(pending.find('article').attributes('aria-busy')).toBe('true')
    expect(pending.text()).toContain('Fetching details…')
    const ready = mountTile({ link: { ...link, metadata_status: 'ready' } })
    expect(ready.find('article').attributes('aria-busy')).toBe('false')
    expect(ready.text()).not.toContain('Fetching details…')
  })
})
