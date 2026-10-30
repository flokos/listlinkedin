import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { createVuetify } from 'vuetify'

const api = vi.hoisted(() => ({ directory: vi.fn(), popularTags: vi.fn() }))
vi.mock('../api', async (original) => ({ ...(await original<typeof import('../api')>()), ...api }))

import type { ListDetail } from '../api'
import ExploreView from './ExploreView.vue'

const vuetify = createVuetify()

function list(title: string, tags: string[] = []): ListDetail {
  return {
    id: title,
    code: title.slice(0, 4).toUpperCase(),
    slug: title.toLowerCase(),
    title,
    description: '',
    image_url: null,
    tags,
    owner: { display_name: 'Theo' },
    link_count: 3,
    updated_at: new Date().toISOString(),
  } as ListDetail
}
const page = (results: ListDetail[], next: string | null = null) => ({
  count: results.length,
  next,
  previous: null,
  results,
})

async function mountAt(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/explore', name: 'explore', component: ExploreView },
      { path: '/l/:code/:slug?', name: 'list', component: { render: () => null } },
      { path: '/g/:code/:slug?', name: 'group', component: { render: () => null } },
      { path: '/lists', name: 'saved-lists', component: { render: () => null } },
      { path: '/signup', name: 'signup', component: { render: () => null } },
    ],
  })
  await router.push(path)
  const wrapper = mount(RouterView, { global: { plugins: [vuetify, router] } })
  await flushPromises()
  return { wrapper, router }
}

/** Navigations take a few ticks: wait until the address is `query`, then for the reload. */
async function navigated(router: Awaited<ReturnType<typeof mountAt>>['router'], query: object) {
  await vi.waitFor(() => expect(router.currentRoute.value.query).toEqual(query))
  await flushPromises()
}

const lastQuery = () => api.directory.mock.lastCall?.slice(0, 2)

beforeEach(() => {
  api.directory.mockReset()
  api.popularTags.mockReset().mockResolvedValue([{ tag: 'dev', count: 4 }])
})

describe('ExploreView', () => {
  it('lists public lists, and a tag narrows the search through the address', async () => {
    api.directory.mockResolvedValue(page([list('Docker tools', ['dev', 'ops'])]))
    const { wrapper, router } = await mountAt('/explore')
    expect(lastQuery()).toEqual(['lists', { q: '', tags: [], ordering: '-updated_at', page: 1 }])
    expect(wrapper.text()).toContain('Docker tools')
    expect(wrapper.text()).toContain('By Theo · 3 links')

    await wrapper.find('button[aria-label="Filter by ops"]').trigger('click')
    await navigated(router, { tags: 'ops' })
    expect(lastQuery()).toEqual([
      'lists',
      { q: '', tags: ['ops'], ordering: '-updated_at', page: 1 },
    ])
    expect(wrapper.find('button[aria-label="Filter by ops"]').attributes('aria-pressed')).toBe(
      'true',
    )
    wrapper.unmount()
  })

  it('searches by best match on Enter, and offers to clear a search that finds nothing', async () => {
    api.directory.mockResolvedValue(page([]))
    const { wrapper, router } = await mountAt('/explore?in=groups')
    const input = wrapper.find('input[type="search"]')
    await input.setValue('kubernetes')
    await wrapper.find('form').trigger('submit')
    await navigated(router, { in: 'groups', q: 'kubernetes' })
    expect(lastQuery()).toEqual([
      'groups',
      { q: 'kubernetes', tags: [], ordering: '-relevance', page: 1 },
    ])
    expect(wrapper.text()).toContain('No groups match')

    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Clear search')!
      .trigger('click')
    await navigated(router, { in: 'groups' })
    expect(wrapper.text()).toContain('No public groups yet')
    wrapper.unmount()
  })

  it('loads the next page on Show more', async () => {
    api.directory
      .mockResolvedValueOnce({ ...page([list('One')], '/next'), count: 2 })
      .mockResolvedValueOnce({ ...page([list('Two')]), count: 2 })
    const { wrapper } = await mountAt('/explore')
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Show more')!
      .trigger('click')
    await flushPromises()
    expect(api.directory.mock.lastCall?.[1].page).toBe(2)
    expect(wrapper.text()).toContain('One')
    expect(wrapper.text()).toContain('Two')
    expect(wrapper.findAll('button').some((b) => b.text() === 'Show more')).toBe(false)
    wrapper.unmount()
  })
})
