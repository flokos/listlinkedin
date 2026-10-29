import { describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

describe('useViewPreference', () => {
  it('defaults to the grid and remembers the list view on this device', async () => {
    localStorage.clear()
    vi.resetModules()
    const { useViewPreference } = await import('./useViewPreference')
    const { view } = useViewPreference()
    expect(view.value).toBe('grid')
    view.value = 'list'
    await nextTick()
    expect(localStorage.getItem('ll:link-view')).toBe('list')

    vi.resetModules()
    const again = await import('./useViewPreference')
    expect(again.useViewPreference().view.value).toBe('list')
    again.useViewPreference().view.value = 'grid'
    await nextTick()
    expect(localStorage.getItem('ll:link-view')).toBeNull()
  })
})
