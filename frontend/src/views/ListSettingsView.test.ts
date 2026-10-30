import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref, shallowRef } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createVuetify } from 'vuetify'

import { ApiError, type ListDetail } from '../api'

const page = vi.hoisted(() => ({ current: undefined as unknown }))
vi.mock('../composables/useListPage', () => ({ useListPage: () => page.current }))
vi.mock('../api', async (original) => ({
  ...(await original<typeof import('../api')>()),
  popularTags: vi.fn().mockResolvedValue([]),
}))

import ListSettingsView from './ListSettingsView.vue'
import { endOfDay } from '../utils/time'

const vuetify = createVuetify()

function fakePage(permissions: string[]) {
  const list = shallowRef<ListDetail>({
    code: 'L',
    title: 'Dev tools',
    description: 'Old',
    tags: ['dev'],
    visibility: 'unlisted',
    expires_at: null,
    image_url: null,
    head_revision: 3,
    permissions,
  } as unknown as ListDetail)
  // Like the real page: the new head (from the ETag) lands before the new content.
  const change = vi.fn(async (changes: Partial<ListDetail>) => {
    list.value = { ...list.value, head_revision: list.value.head_revision + 1 }
    await Promise.resolve()
    list.value = { ...list.value, ...changes }
  })
  page.current = {
    list,
    status: ref('ready'),
    loadError: ref(),
    can: (p: string) => list.value.permissions.includes(p),
    load: vi.fn(),
    change,
    setImage: vi.fn(),
    removeList: vi.fn(),
  }
  return { list, change }
}

async function mountPage() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/l/:code/settings', component: ListSettingsView, props: true },
      { path: '/l/:code', name: 'list', component: { render: () => null } },
      { path: '/lists', name: 'saved-lists', component: { render: () => null } },
    ],
  })
  await router.push('/l/L/settings')
  const wrapper = mount(ListSettingsView, {
    props: { code: 'L' },
    global: { plugins: [vuetify, router] },
  })
  await flushPromises()
  const headings = () => wrapper.findAll('h2').map((h) => h.text())
  const button = (text: string) => wrapper.findAll('button').find((b) => b.text() === text)!
  return { wrapper, headings, button }
}

beforeEach(() => vi.clearAllMocks())

describe('ListSettingsView', () => {
  it("tells a viewer they can't change anything", async () => {
    fakePage(['view'])
    const { wrapper, headings } = await mountPage()
    expect(wrapper.text()).toContain("You can't change this list's settings")
    expect(headings()).toEqual([])
  })

  it('shows an editor only what editors may change, and saves the description', async () => {
    const { change } = fakePage(['view', 'edit', 'upload', 'tags'])
    const { wrapper, headings } = await mountPage()
    expect(headings()).toEqual(['Name and description', 'Image', 'Tags'])

    await wrapper.find('textarea').setValue('  Tools we use  ')
    await wrapper.findAll('form')[0]!.trigger('submit')
    await flushPromises()
    expect(change).toHaveBeenCalledWith({ title: 'Dev tools', description: 'Tools we use' })
    expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe('Tools we use')
  })

  it('explains a save refused because the list changed meanwhile', async () => {
    const { change } = fakePage(['view', 'edit'])
    change.mockRejectedValueOnce(new ApiError(412, { head_revision: 4 }))
    const { wrapper } = await mountPage()
    await wrapper.find('textarea').setValue('Mine')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('Someone changed this list while you were editing')
  })

  it('gives the owner sharing, expiry and delete, and sets an expiry date', async () => {
    const { change } = fakePage(['view', 'edit', 'upload', 'tags', 'settings', 'delete'])
    const { wrapper, headings } = await mountPage()
    expect(headings()).toEqual([
      'Name and description',
      'Image',
      'Tags',
      'Sharing',
      'Expiry',
      'Delete this list',
    ])
    await wrapper.findAll('input[type="radio"]')[1]!.setValue(true)
    await flushPromises()
    await wrapper.find('input[type="date"]').setValue('2099-01-31')
    const forms = wrapper.findAll('form')
    await forms[forms.length - 1]!.trigger('submit')
    await flushPromises()
    expect(change).toHaveBeenCalledWith({ expires_at: endOfDay('2099-01-31') })
  })
})
