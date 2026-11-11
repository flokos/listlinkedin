import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { type GroupSummary, groupSummary } from '../lib/lists'
import { type ListSummary, saveConnection } from '../lib/storage'
import { ADA, json } from '../test/fakeBrowser'
import { apiGroup, apiList, listSummary, site } from '../test/site'
import GroupManage from './GroupManage.vue'

const GROUP = '/api/v2/groups/G/'
const REORDER = `POST ${GROUP}reorder/`
const none = () => new Response(null, { status: 204 })
const group = (extra: Record<string, unknown> = {}) =>
  groupSummary(apiGroup('G', { title: 'Team', list_count: 3, ...extra }) as never)
const three = () => [listSummary('A'), listSummary('B'), listSummary('C')]

async function open(props: Partial<InstanceType<typeof GroupManage>['$props']> = {}) {
  const wrapper = mount(GroupManage, {
    attachTo: document.body,
    props: { group: group(), lists: three(), mine: [...three(), listSummary('D')], ...props },
  })
  await flushPromises()
  // The parent keeps the group and its lists: play its part.
  const follow = async () => {
    const lists = wrapper.emitted('lists')?.at(-1)?.[0] as ListSummary[] | undefined
    const changed = wrapper.emitted('changed')?.at(-1)?.[0] as GroupSummary | undefined
    await wrapper.setProps({ ...(lists ? { lists } : {}), ...(changed ? { group: changed } : {}) })
  }
  const button = (text: string) => wrapper.findAll('button').find((b) => b.text() === text)
  const names = () => wrapper.findAll('.manage__name').map((name) => name.text())
  const note = () => wrapper.find('.ll-notice')
  return { wrapper, follow, button, names, note }
}

beforeEach(() => saveConnection(ADA))

describe('GroupManage', () => {
  it('offers only what the server says this account may do', async () => {
    site({})
    const viewer = await open({ group: group({ permissions: ['view'] }) })
    expect(viewer.wrapper.find('#manage-name').exists()).toBe(false)
    expect(viewer.wrapper.find('#manage-visibility').exists()).toBe(false)
    expect(viewer.wrapper.find('#manage-add').exists()).toBe(false)
    expect(viewer.wrapper.find('.manage__move').exists()).toBe(false)
    expect(viewer.button('Delete group…')).toBeUndefined()
    expect(viewer.wrapper.find('[data-list="A"]').attributes('draggable')).toBeUndefined()

    // An editor: the name, the lists and their order; not who can open it, not deleting.
    const editor = await open({ group: group({ permissions: ['view', 'edit', 'add_list'] }) })
    expect(editor.wrapper.find('#manage-name').exists()).toBe(true)
    expect(editor.wrapper.find('#manage-add').exists()).toBe(true)
    expect(editor.wrapper.findAll('.manage__move')).toHaveLength(6)
    expect(editor.wrapper.find('#manage-visibility').exists()).toBe(false)
    expect(editor.button('Delete group…')).toBeUndefined()
  })

  it('renames the group', async () => {
    const { calls, bodies } = site({
      [`PATCH ${GROUP}`]: () => json(apiGroup('G', { title: 'Crew' })),
    })
    const { wrapper, button, note } = await open()
    expect(button('Rename')!.attributes('disabled')).toBeDefined() // the name as it is

    await wrapper.find('#manage-name').setValue('  Crew ')
    await button('Rename')!.trigger('click')
    await flushPromises()

    expect(bodies[calls.indexOf(`PATCH ${GROUP}`)]).toEqual({ title: 'Crew' })
    expect(wrapper.emitted('changed')![0]).toEqual([expect.objectContaining({ title: 'Crew' })])
    expect(note().text()).toBe('The group is now called “Crew”.')
  })

  it('changes who can open the group only when the user chooses and confirms', async () => {
    const { calls, bodies } = site({
      [`PATCH ${GROUP}`]: () => json(apiGroup('G', { visibility: 'unlisted' })),
    })
    const { wrapper, button, note } = await open()

    await wrapper.find('#manage-visibility').setValue('unlisted')
    expect(calls).toEqual([]) // choosing is not yet changing
    await button('Change')!.trigger('click')
    await flushPromises()

    expect(bodies[0]).toEqual({ visibility: 'unlisted' })
    expect(note().text()).toContain('Anyone with this link can view the group')
    expect(note().text()).toContain('Its lists are as they were.')
  })

  it("says why and changes nothing when the site won't", async () => {
    site({
      [`PATCH ${GROUP}`]: () =>
        json({ detail: 'Verify your email address to make this public.' }, 403),
    })
    const { wrapper, button, note } = await open()
    await wrapper.find('#manage-visibility').setValue('public')
    await button('Change')!.trigger('click')
    await flushPromises()

    expect(note().text()).toBe('Verify your email address to make this public.')
    expect((wrapper.find('#manage-visibility').element as HTMLSelectElement).value).toBe('private')
    expect(wrapper.emitted('changed')).toBeUndefined()
  })

  it('adds a list that is not in the group yet, and shows the group as the site has it', async () => {
    const { calls, bodies } = site({
      [`POST ${GROUP}lists/`]: () => json(apiList('D'), 201),
      [`GET ${GROUP}lists/`]: () => json(['A', 'B', 'C', 'D'].map((code) => apiList(code))),
    })
    const { wrapper, follow, button, names, note } = await open()
    expect(wrapper.findAll('#manage-add option').map((option) => option.text())).toEqual([
      'Choose a list',
      'List D', // A, B and C are in it already
    ])

    await wrapper.find('#manage-add').setValue('D')
    await button('Add')!.trigger('click')
    await flushPromises()
    await follow()

    expect(bodies[calls.indexOf(`POST ${GROUP}lists/`)]).toEqual({ list: 'D' })
    expect(names()).toEqual(['List A', 'List B', 'List C', 'List D'])
    expect(wrapper.emitted('changed')!.at(-1)).toEqual([expect.objectContaining({ listCount: 4 })])
    expect(note().text()).toBe('Added “List D” to the group.')
    expect(wrapper.find('#manage-add').exists()).toBe(false) // nothing left to add
  })

  it('moves a list by the arrows and by dragging, in the order the site answers with', async () => {
    const orders = [
      ['B', 'A', 'C'],
      ['A', 'C', 'B'],
    ]
    const { calls, bodies } = site({
      [REORDER]: () => json(orders.shift()!.map((code) => apiList(code))),
    })
    const { wrapper, follow, names, note } = await open()

    await wrapper.find('[aria-label="Move List B up"]').trigger('click')
    await flushPromises()
    await follow()
    expect(bodies[0]).toEqual({ list: 'B', to_index: 0 })
    expect(names()).toEqual(['List B', 'List A', 'List C'])
    expect(note().text()).toBe('“List B” is now 1 of 3.')

    const dataTransfer = { setData: vi.fn(), effectAllowed: '', dropEffect: '' }
    const row = (code: string) => wrapper.find(`[data-list="${code}"]`)
    await row('B').trigger('dragstart', { dataTransfer })
    await row('C').trigger('dragover', { dataTransfer })
    expect(row('C').classes()).toContain('manage__list--over')
    await row('C').trigger('drop', { dataTransfer })
    await flushPromises()
    await follow()

    expect(bodies[1]).toEqual({ list: 'B', to_index: 2 })
    expect(names()).toEqual(['List A', 'List C', 'List B'])
    expect(calls.filter((call) => call === REORDER)).toHaveLength(2)
  })

  it('takes a list out only after it was asked about, and leaves the list alone', async () => {
    const OUT = `DELETE ${GROUP}lists/B/`
    const { calls } = site({ [OUT]: none })
    const { wrapper, follow, button, names, note } = await open()

    await wrapper.find('[aria-label="Take List B out…"]').trigger('click')
    await flushPromises()
    expect(calls).toEqual([]) // asked, not done
    await button('Keep')!.trigger('click')
    await flushPromises()
    expect(calls).toEqual([])

    await wrapper.find('[aria-label="Take List B out…"]').trigger('click')
    await wrapper.find('[aria-label="Take List B out of the group"]').trigger('click')
    await flushPromises()
    await follow()

    expect(calls).toEqual([OUT]) // the group's entry only: nothing is sent about the list
    expect(names()).toEqual(['List A', 'List C'])
    expect(note().text()).toContain('The list itself is as it was.')
    expect(wrapper.emitted('changed')!.at(-1)).toEqual([expect.objectContaining({ listCount: 2 })])
  })

  it('deletes the group only after it was asked about', async () => {
    const { calls } = site({ [`DELETE ${GROUP}`]: none })
    const { wrapper, button } = await open()

    await button('Delete group…')!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Its lists stay as they are')
    expect(document.activeElement?.textContent?.trim()).toBe('Keep')
    await button('Keep')!.trigger('click')
    await flushPromises()
    expect(calls).toEqual([])

    await button('Delete group…')!.trigger('click')
    await button('Delete group')!.trigger('click')
    await flushPromises()

    expect(calls).toEqual([`DELETE ${GROUP}`])
    expect(wrapper.emitted('deleted')).toHaveLength(1)
  })

  it('reports a connection that is over, and says when it is done', async () => {
    site({ [REORDER]: () => json({ detail: 'Sign in.' }, 401) })
    const { wrapper, button } = await open()
    await wrapper.find('[aria-label="Move List B up"]').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('disconnected')).toBeTruthy()

    await button('Done')!.trigger('click')
    expect(wrapper.emitted('done')).toHaveLength(1)
  })
})
