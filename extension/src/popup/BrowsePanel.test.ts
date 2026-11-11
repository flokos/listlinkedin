import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { cacheLists, saveConnection } from '../lib/storage'
import { ADA, json } from '../test/fakeBrowser'
import { apiGroup, apiList, listSummary, page, type Route, site } from '../test/site'
import BrowsePanel from './BrowsePanel.vue'

const LISTS = 'GET /api/v2/lists/'
const GROUPS = 'GET /api/v2/groups/'
const noGroups: Record<string, Route> = { [GROUPS]: () => page([]) }

// The list's own view has its tests (ListDetail.test.ts).
const ListDetail = {
  name: 'ListDetail',
  props: ['list', 'groups'],
  emits: ['back', 'changed', 'disconnected'],
  template: '<div class="list-detail">{{ list.title }} · {{ list.visibility }}</div>',
}

async function open() {
  const wrapper = mount(BrowsePanel, {
    attachTo: document.body,
    global: { stubs: { ListDetail } },
  })
  await flushPromises()
  const titles = () => wrapper.findAll('.browse__title').map((title) => title.text())
  const row = (title: string) =>
    wrapper.findAll('.browse__list').find((button) => button.text().includes(title))!
  const button = (text: string) => wrapper.findAll('button').find((b) => b.text() === text)
  return { wrapper, titles, row, button }
}

function clipboard() {
  const written: string[] = []
  vi.stubGlobal('navigator', {
    clipboard: { writeText: vi.fn(async (text: string) => void written.push(text)) },
  })
  return written
}

beforeEach(() => saveConnection(ADA))

describe('BrowsePanel', () => {
  it('lists every list of the account, also the ones it can only view', async () => {
    site({
      ...noGroups,
      [LISTS]: () =>
        page([
          apiList('A', { title: 'Reading', link_count: 1, visibility: 'unlisted' }),
          apiList('V', { title: 'Shared with me', permissions: ['view'] }),
        ]),
    })
    const { wrapper, titles } = await open()

    expect(titles()).toEqual(['Reading', 'Shared with me'])
    expect(wrapper.text()).toContain('1 link · Anyone with the link')
    expect(wrapper.text()).toContain('3 links · Only people you add')
    expect(wrapper.find('select').exists()).toBe(false) // no groups, no filter
  })

  it('opens a list, and comes back to the lists', async () => {
    site({ ...noGroups, [LISTS]: () => page([apiList('A'), apiList('B')]) })
    const { wrapper, titles, row } = await open()

    await row('List B').trigger('click')
    expect(wrapper.find('.list-detail').text()).toBe('List B · private')
    expect(wrapper.find('.browse__lists').exists()).toBe(false)

    wrapper.findComponent(ListDetail).vm.$emit('back')
    await flushPromises()
    expect(titles()).toEqual(['List A', 'List B'])
  })

  it('shows a change made in the list everywhere', async () => {
    site({ ...noGroups, [LISTS]: () => page([apiList('A')]) })
    const { wrapper, row } = await open()
    await row('List A').trigger('click')

    wrapper
      .findComponent(ListDetail)
      .vm.$emit('changed', listSummary('A', { visibility: 'unlisted' }))
    await flushPromises()
    expect(wrapper.find('.list-detail').text()).toBe('List A · unlisted')

    wrapper.findComponent(ListDetail).vm.$emit('back')
    await flushPromises()
    expect(wrapper.text()).toContain('3 links · Anyone with the link')
  })

  it("shows a group's lists in its order, and copies the group's link without changing it", async () => {
    const written = clipboard()
    const { calls } = site({
      [LISTS]: () => page([apiList('A'), apiList('B')]),
      [GROUPS]: () => page([apiGroup('G', { title: 'Team', visibility: 'unlisted' })]),
      'GET /api/v2/groups/G/lists/': () =>
        json([apiList('B'), apiList('V', { permissions: ['view'] })]),
    })
    const { wrapper, titles, button } = await open()

    await wrapper.find('select').setValue('G')
    await flushPromises()

    expect(titles()).toEqual(['List B', 'List V'])
    expect(wrapper.text()).toContain('2 lists · Anyone with the link')
    expect(wrapper.find('.browse__group a').attributes('href')).toBe(
      'https://lists.example.test/g/G',
    )

    await button('Copy group link')!.trigger('click')
    await flushPromises()
    expect(written).toEqual(['https://lists.example.test/g/G'])
    expect(wrapper.find('[role="status"]').text()).toBe(
      'Group link copied. Anyone with this link can view the group, but not change it.',
    )
    expect(calls.every((call) => call.startsWith('GET '))).toBe(true) // nothing was changed
  })

  it('searches when there are many lists', async () => {
    site({
      ...noGroups,
      [LISTS]: () =>
        page([
          ...'ABCDEF'.split('').map((code) => apiList(code)),
          apiList('R', { title: 'Recipes' }),
        ]),
    })
    const { wrapper, titles } = await open()

    await wrapper.find('input[type="search"]').setValue('recip')
    expect(titles()).toEqual(['Recipes'])
    await wrapper.find('input[type="search"]').setValue('nothing like this')
    expect(wrapper.text()).toContain('No list matches.')
  })

  it('shows the lists from last time when the site cannot be reached', async () => {
    await cacheLists([listSummary('A')])
    site({ [LISTS]: () => new TypeError('Failed to fetch') })
    const { wrapper, titles } = await open()

    expect(titles()).toEqual(['List A'])
    expect(wrapper.find('[role="status"]').text()).toContain('as they were last time')
  })

  it('goes back to connecting when the site has ended the connection', async () => {
    site({ [LISTS]: () => json({ detail: 'Sign in.' }, 401) })
    const { wrapper } = await open()
    expect(wrapper.emitted('disconnected')).toHaveLength(1)
  })

  it('says so when the account has no lists', async () => {
    site({ ...noGroups, [LISTS]: () => page([]) })
    const { wrapper } = await open()
    expect(wrapper.text()).toContain('You have no lists yet.')
  })
})
