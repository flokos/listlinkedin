import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { defineComponent, h, type WritableComputedRef } from 'vue'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'

import { useQueryDialog } from './useQueryDialog'

let dialog: WritableComputedRef<boolean>
const Page = defineComponent(() => {
  dialog = useQueryDialog('share')
  return () => h('p')
})

async function at(...paths: string[]) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { render: () => null } },
      { path: '/l/:code', component: Page },
    ],
  })
  for (const path of paths) await router.push(path)
  mount(RouterView, { global: { plugins: [router] } })
  await flushPromises()
  const settled = (path: string) =>
    vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe(path))
  return { router, settled }
}

describe('useQueryDialog', () => {
  it('opens by adding a history entry and closes by going back once, even if told twice', async () => {
    const { router, settled } = await at('/', '/l/abc')
    dialog.value = true
    await settled('/l/abc?dialog=share')
    expect(dialog.value).toBe(true)

    dialog.value = false
    expect(dialog.value).toBe(false) // at once, while going back
    dialog.value = false // a dialog's own close event, before the navigation ends
    dialog.value = true // or its model bouncing back
    await settled('/l/abc')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/l/abc') // not back on "/"
    expect(dialog.value).toBe(false)
  })

  it('opened from a link, closing stays on the page', async () => {
    const { settled } = await at('/', '/l/abc?dialog=share&x=1')
    expect(dialog.value).toBe(true)
    dialog.value = false
    await settled('/l/abc?x=1')
  })
})
