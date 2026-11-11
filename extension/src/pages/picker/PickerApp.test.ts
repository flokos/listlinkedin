import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { getNewListVisibility, markUsed, saveConnection } from '../../lib/storage'
import { ADA, browser, json } from '../../test/fakeBrowser'
import { apiList, page, site } from '../../test/site'
import PickerApp from './PickerApp.vue'

const LISTS = 'GET /api/v2/lists/'
const TABS = [
  { url: 'https://example.com/a', title: 'Alpha' },
  { url: 'https://example.com/b', title: 'Beta' },
  { url: 'about:newtab', title: 'New tab' },
  { url: 'https://example.com/c', title: 'Gamma' },
]

async function open(search = '?source=tabs') {
  window.history.replaceState(null, '', `/picker.html${search}`)
  const wrapper = mount(PickerApp, { attachTo: document.body })
  await flushPromises()
  const button = (text: string) => wrapper.findAll('button').find((b) => b.text() === text)
  const titles = () => wrapper.findAll('.picker__title').map((title) => title.text())
  const tick = (title: string) =>
    wrapper
      .findAll('.picker__page')
      .find((label) => label.text().includes(title))!
      .find('input')
      .setValue(true)
  const save = async () => {
    await wrapper.find('form').trigger('submit')
    await flushPromises()
  }
  return { wrapper, button, titles, tick, save }
}

beforeEach(async () => {
  await saveConnection(ADA)
  browser().tabs.query.mockResolvedValue(TABS)
})
afterEach(() => void vi.useRealTimers())

describe('the picker', () => {
  it('reads nothing until the user allows it, then lists the open tabs', async () => {
    site({ [LISTS]: () => page([apiList('A')]) })
    const { wrapper, button, titles } = await open()

    expect(wrapper.text()).toContain('only the pages you tick are sent')
    expect(browser().tabs.query).not.toHaveBeenCalled()
    expect(wrapper.find('form').exists()).toBe(false)

    await button('Allow reading your open tabs')!.trigger('click')
    await flushPromises()

    expect(browser().permissions.request).toHaveBeenCalledWith({ permissions: ['tabs'] })
    expect(titles()).toEqual(['Alpha', 'Beta', 'Gamma']) // not the tab that can't be saved
  })

  it('says so when the user refuses', async () => {
    site({ [LISTS]: () => page([apiList('A')]) })
    browser().permissions.request.mockResolvedValue(false)
    const { wrapper, button } = await open()
    await button('Allow reading your open tabs')!.trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').text()).toContain("can't show your open tabs")
    expect(browser().tabs.query).not.toHaveBeenCalled()
  })

  it('saves the ticked pages, in the order shown, to the list used last', async () => {
    browser().permissions.granted.add('tabs')
    await markUsed('B')
    const { calls, bodies } = site({
      [LISTS]: () => page([apiList('A'), apiList('B'), apiList('V', { permissions: ['view'] })]),
      'POST /api/v2/lists/B/links/batch/': () =>
        json({ added: [{}], skipped: [{ index: 0, reason: 'duplicate' }] }),
    })
    const { wrapper, tick, save } = await open()

    expect(wrapper.findAll('#picker-list option').map((option) => option.text())).toEqual([
      'List B', // used last: first, and chosen
      'List A',
      'A new list…',
    ])
    expect((wrapper.find('button[type="submit"]').element as HTMLButtonElement).disabled).toBe(true)

    await tick('Gamma')
    await tick('Alpha')
    expect(wrapper.find('button[type="submit"]').text()).toBe('Save 2 pages')
    await save()

    expect(bodies[calls.indexOf('POST /api/v2/lists/B/links/batch/')]).toEqual({
      links: [
        { destination_url: 'https://example.com/a', title: 'Alpha' },
        { destination_url: 'https://example.com/c', title: 'Gamma' },
      ],
    })
    const told = wrapper.find('[role="status"]')
    expect(told.text()).toContain('1 page saved, 1 was already there.')
    expect(told.find('a').attributes('href')).toBe('https://lists.example.test/l/B')
    expect(wrapper.findAll('input:checked')).toHaveLength(0) // ready for the next pick
  })

  it('selects everything shown, and narrows the tabs by what is typed', async () => {
    browser().permissions.granted.add('tabs')
    site({ [LISTS]: () => page([apiList('A')]) })
    const { wrapper, titles } = await open()

    await wrapper.find('#picker-search').setValue('et')
    expect(titles()).toEqual(['Beta'])
    await wrapper.find('.picker__all input').setValue(true)
    await wrapper.find('#picker-search').setValue('')
    expect(wrapper.find('button[type="submit"]').text()).toBe('Save 1 page')

    await wrapper.find('.picker__all input').setValue(true)
    expect(wrapper.find('button[type="submit"]').text()).toBe('Save 3 pages')
  })

  it('makes a new list and saves into it', async () => {
    browser().permissions.granted.add('tabs')
    const { calls, bodies } = site({
      [LISTS]: () => page([]),
      'POST /api/v2/lists/': () => json(apiList('N', { title: 'Reading', link_count: 0 }), 201),
      'POST /api/v2/lists/N/links/batch/': () => json({ added: [{}, {}, {}], skipped: [] }),
    })
    const { wrapper, save } = await open()

    await wrapper.find('.picker__all input').setValue(true)
    expect((wrapper.find('button[type="submit"]').element as HTMLButtonElement).disabled).toBe(true)
    await wrapper.find('#picker-new-list').setValue('Reading')
    // The user's choice, made here: the list is made that way, and the choice is kept.
    await wrapper.find('#picker-new-access').setValue('unlisted')
    expect(wrapper.find('#picker-new-access-meaning').text()).toBe(
      'Anyone with this link can view the list, but not change it.',
    )
    await save()

    expect(bodies[calls.indexOf('POST /api/v2/lists/')]).toEqual({
      title: 'Reading',
      visibility: 'unlisted',
    })
    expect(await getNewListVisibility()).toBe('unlisted')
    expect(wrapper.find('[role="status"]').text()).toContain('3 pages saved.')
    expect(wrapper.find('[role="status"] a').text()).toBe('Open “Reading”')
  })

  it('warns when more is ticked than the list has room for', async () => {
    browser().permissions.granted.add('tabs')
    site({ [LISTS]: () => page([apiList('A', { link_count: 98 })]) })
    const { wrapper } = await open()
    await wrapper.find('.picker__all input').setValue(true)
    expect(wrapper.find('[role="note"]').text()).toContain('room for 2')
  })

  it('says how far it got when the site stops it', async () => {
    browser().permissions.granted.add('tabs')
    site({
      [LISTS]: () => page([apiList('A')]),
      'POST /api/v2/lists/A/links/batch/': () =>
        json({ detail: 'Slow down.' }, 429, { 'Retry-After': '120' }),
    })
    const { wrapper, save } = await open()
    await wrapper.find('.picker__all input').setValue(true)
    await save()
    const told = wrapper.find('[role="status"]')
    expect(told.text()).toContain("0 pages saved, 3 weren't sent.")
    expect(told.text()).toContain('Try again in 2 minutes.')
  })

  it('searches the history through the browser, after its own permission', async () => {
    vi.useFakeTimers()
    site({ [LISTS]: () => page([apiList('A')]) })
    browser().history.search.mockImplementation(async ({ text }) =>
      text === 'docs'
        ? [{ url: 'https://example.com/docs', title: 'Docs', lastVisitTime: 2 }]
        : [
            { url: 'https://example.com/docs', title: 'Docs', lastVisitTime: 2 },
            { url: 'https://example.com/news', title: 'News', lastVisitTime: 3 },
          ],
    )
    const { wrapper, button, titles } = await open('?source=history')

    expect(browser().history.search).not.toHaveBeenCalled()
    await button('Allow reading your browsing history')!.trigger('click')
    await flushPromises()
    expect(browser().permissions.request).toHaveBeenCalledWith({ permissions: ['history'] })
    expect(titles()).toEqual(['News', 'Docs'])

    await wrapper.find('#picker-search').setValue('docs')
    await vi.advanceTimersByTimeAsync(300)
    await flushPromises()
    expect(titles()).toEqual(['Docs'])
  })

  it('switches between the two sources', async () => {
    browser().permissions.granted.add('tabs')
    site({ [LISTS]: () => page([apiList('A')]) })
    const { wrapper, button, titles } = await open()
    expect(button('Open tabs')!.attributes('aria-pressed')).toBe('true')

    await button('History')!.trigger('click')
    await flushPromises()
    expect(titles()).toEqual([])
    expect(wrapper.text()).toContain('Allow reading your browsing history')
  })

  it('offers to connect first', async () => {
    await browser().storage.local.remove('connection')
    const { wrapper } = await open()
    expect(wrapper.text()).toContain('Connect this browser')
    expect(browser().tabs.query).not.toHaveBeenCalled()
  })
})
