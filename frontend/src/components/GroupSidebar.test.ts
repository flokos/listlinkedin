import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createVuetify } from 'vuetify'
import { VLayout } from 'vuetify/components'

import type { GroupList } from '../api'
import GroupSidebar from './GroupSidebar.vue'

const vuetify = createVuetify()
const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/', component: { render: () => null } },
    { path: '/g/:code/l/:listCode', name: 'group-list', component: { render: () => null } },
  ],
})

const item = (code: string, title: string, shownToAll = true) =>
  ({ code, title, image_url: null, shown_to_all: shownToAll }) as GroupList
const lists = [item('AAA1', 'Backend tools'), item('BBB2', 'AI tools'), item('CCC3', 'Mine', false)]

async function mountSidebar(props: Record<string, unknown> = {}, reordering = false) {
  const state = { reordering: ref(reordering) }
  // A drawer needs a layout around it.
  const Host = defineComponent(
    () => () =>
      h(VLayout, () =>
        h(GroupSidebar, {
          modelValue: true,
          reordering: state.reordering.value,
          'onUpdate:reordering': (v: boolean) => (state.reordering.value = v),
          mode: 'permanent',
          groupTitle: 'Dev Portal',
          groupCode: 'GRP',
          lists,
          currentCode: 'BBB2',
          canEdit: true,
          busy: false,
          ...props,
        }),
      ),
  )
  router.push('/')
  await router.isReady()
  const wrapper = mount(Host, { global: { plugins: [vuetify, router] }, attachTo: document.body })
  await flushPromises()
  return { wrapper, sidebar: wrapper.findComponent(GroupSidebar), state }
}

describe('GroupSidebar', () => {
  it('links every list it is given, marking the current one', async () => {
    const { wrapper } = await mountSidebar()
    const nav = wrapper.find('nav[aria-label="Lists in Dev Portal"]')
    const links = nav.findAll('a')
    expect(links.map((a) => a.attributes('href'))).toEqual([
      '/g/GRP/l/AAA1',
      '/g/GRP/l/BBB2',
      '/g/GRP/l/CCC3',
    ])
    expect(links.map((a) => a.attributes('aria-current'))).toEqual([undefined, 'page', undefined])
    // A list only you see is marked, in text as well as with the icon.
    expect(links[2]!.text()).toContain('not everyone in the group sees this list')
    expect(links[0]!.text()).not.toContain('not everyone')
    wrapper.unmount()
  })

  it('moves and removes lists with buttons while reordering', async () => {
    const { wrapper, sidebar } = await mountSidebar({}, true)
    expect(wrapper.find('nav a').exists()).toBe(false)
    const button = (name: string) => wrapper.find(`button[aria-label="${name}"]`)
    expect(button('Move Backend tools up').attributes('disabled')).toBeDefined()
    expect(button('Move Mine down').attributes('disabled')).toBeDefined()

    await button('Move AI tools up').trigger('click')
    await button('Move Backend tools down').trigger('click')
    await button('Remove Mine from the group').trigger('click')
    expect(sidebar.emitted('move')).toEqual([
      [lists[1], 0],
      [lists[0], 1],
    ])
    expect(sidebar.emitted('remove')).toEqual([[lists[2]]])

    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Done')!
      .trigger('click')
    expect(sidebar.emitted('update:reordering')).toEqual([[false]])
    wrapper.unmount()
  })

  it('waits for a move to finish before offering another', async () => {
    const { wrapper } = await mountSidebar({ busy: true }, true)
    for (const b of wrapper.findAll('.ll-group-sidebar__row button'))
      expect(b.attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })
})
