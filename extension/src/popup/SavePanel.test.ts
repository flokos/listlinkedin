import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { cacheLists, markUsed, saveConnection } from '../lib/storage'
import { ADA, browser, json } from '../test/fakeBrowser'
import { apiGroup, apiList, listSummary as summary, page, type Route, site } from '../test/site'
import SavePanel from './SavePanel.vue'

const TAB = { url: 'https://example.com/article', title: 'An article' }
const LISTS = 'GET /api/v2/lists/'
const GROUPS = 'GET /api/v2/groups/'
const noGroups: Record<string, Route> = { [GROUPS]: () => page([]) }

async function open(tab: { url?: string; title?: string } = TAB) {
  browser().tabs.query.mockResolvedValue([tab])
  const wrapper = mount(SavePanel, { attachTo: document.body })
  await flushPromises()
  const titles = () => wrapper.findAll('.picker__title').map((title) => title.text())
  const choose = (title: string) =>
    wrapper
      .findAll('label')
      .find((label) => label.text().startsWith(title))!
      .find('input')
      .setValue(true)
  const button = (text: string) => wrapper.findAll('button').find((b) => b.text() === text)
  const save = async () => {
    await wrapper.find('form').trigger('submit')
    await flushPromises()
  }
  return { wrapper, titles, choose, button, save }
}

beforeEach(() => saveConnection(ADA))

describe('SavePanel', () => {
  it("saves the tab's page, with the title as edited, to the chosen list", async () => {
    const { calls, bodies } = site({
      ...noGroups,
      [LISTS]: () => page([apiList('A'), apiList('V', { permissions: ['view'] }), apiList('B')]),
      'POST /api/v2/lists/B/links/': () => json({ id: 'l1', short_url: null }, 201),
    })
    const { wrapper, titles, choose, button, save } = await open()

    expect((wrapper.find('#save-title').element as HTMLInputElement).value).toBe('An article')
    expect(wrapper.text()).toContain('https://example.com/article')
    expect(titles()).toEqual(['List A', 'List B']) // not the list this account can only view
    expect(button('Save')!.attributes('disabled')).toBeDefined() // nothing chosen yet

    await wrapper.find('#save-title').setValue('A better title')
    await choose('List B')
    await save()

    expect(calls.at(-1)).toBe('POST /api/v2/lists/B/links/')
    expect(bodies.at(-1)).toEqual({
      destination_url: 'https://example.com/article',
      title: 'A better title',
    })
    expect(wrapper.find('[role="status"]').text()).toBe('Saved to List B.')
    expect(wrapper.find('a').attributes('href')).toBe('https://lists.example.test/l/B')
  })

  it('copies the short link of the page it just saved, and says who it works for', async () => {
    const written: string[] = []
    vi.stubGlobal('navigator', {
      clipboard: { writeText: vi.fn(async (text: string) => void written.push(text)) },
    })
    site({
      ...noGroups,
      [LISTS]: () => page([apiList('A')]),
      'POST /api/v2/lists/A/links/': () =>
        json({ id: 'l1', short_url: 'https://lists.example.test/r/abc' }, 201),
    })
    const { wrapper, choose, button, save } = await open()
    await choose('List A')
    await save()

    await button('Copy short link')!.trigger('click')
    await flushPromises()

    expect(written).toEqual(['https://lists.example.test/r/abc'])
    expect(wrapper.find('.save__copied').text()).toBe(
      'Short link copied. Only people you add can open this link.',
    )
  })

  it('offers the lists saved to last first, with the latest already chosen', async () => {
    await cacheLists([
      { ...summary('A'), title: 'List A' },
      { ...summary('B'), title: 'List B' },
      { ...summary('C'), title: 'List C' },
    ])
    await markUsed('C')
    await markUsed('B')
    const { calls } = site({
      ...noGroups,
      [LISTS]: () => page([apiList('A'), apiList('B'), apiList('C')]),
      'POST /api/v2/lists/B/links/': () => json({ id: 'l1', short_url: null }, 201),
    })
    const { wrapper, titles, save } = await open()

    expect(titles()).toEqual(['List B', 'List C', 'List A'])
    await save() // one action: the list used last is chosen

    expect(calls.at(-1)).toBe('POST /api/v2/lists/B/links/')
    expect(wrapper.text()).toContain('Saved to List B')
  })

  it("says why, in the server's words, when the page is already in the list", async () => {
    site({
      ...noGroups,
      [LISTS]: () => page([apiList('A')]),
      'POST /api/v2/lists/A/links/': () =>
        json({ destination_url: ['This URL is already in the list.'], code: 'invalid' }, 400),
    })
    const { wrapper, choose, save } = await open()
    await choose('List A')
    await save()

    expect(wrapper.find('[role="status"]').text()).toBe('This URL is already in the list.')
    expect(wrapper.find('form').exists()).toBe(true) // still here, to pick another list
  })

  it('reuses the same key when the same page is saved to the same list again', async () => {
    const keys: (string | undefined)[] = []
    let answers = 0
    site({
      ...noGroups,
      [LISTS]: () => page([apiList('A')]),
      'POST /api/v2/lists/A/links/': (init) => {
        keys.push((init.headers as Record<string, string>)['Idempotency-Key'])
        answers += 1
        return answers === 1 ? new TypeError('Failed to fetch') : json({ id: 'l1' }, 201)
      },
    })
    const { wrapper, choose, save } = await open()
    await choose('List A')
    await save()
    expect(wrapper.find('[role="alert"]').text()).toContain("Couldn't reach listlinkedin")
    await save()

    expect(keys[0]).toMatch(/^[0-9a-f-]{36}$/)
    expect(keys[1]).toBe(keys[0])
    expect(wrapper.text()).toContain('Saved to List A')
  })

  it("explains pages that can't be saved and offers nothing to save them to", async () => {
    const { calls } = site({ ...noGroups, [LISTS]: () => page([apiList('A')]) })
    const { wrapper, button } = await open({ url: 'chrome://extensions/', title: 'Extensions' })

    expect(wrapper.find('[role="status"]').text()).toContain('Only web pages')
    expect(wrapper.find('fieldset').exists()).toBe(false)
    expect(button('Save')).toBeUndefined()
    expect(calls.filter((call) => call.startsWith('POST'))).toEqual([])
  })

  it('goes back to connecting when the site has ended the connection', async () => {
    site({ [LISTS]: () => json({ detail: 'Sign in.', code: 'not_authenticated' }, 401) })
    const { wrapper } = await open()
    expect(wrapper.emitted('disconnected')).toHaveLength(1)
  })

  it('shows the lists from last time when the site cannot be reached', async () => {
    await cacheLists([summary('A')])
    site({ [LISTS]: () => new TypeError('Failed to fetch') })
    const { wrapper, titles } = await open()

    expect(titles()).toEqual(['List A'])
    expect(wrapper.find('[role="status"]').text()).toContain('as they were last time')
  })

  it('makes a new list and chooses it', async () => {
    const { calls, bodies } = site({
      ...noGroups,
      [LISTS]: () => page([apiList('A')]),
      'POST /api/v2/lists/': () => json(apiList('N', { title: 'Reading', link_count: 0 }), 201),
      'POST /api/v2/lists/N/links/': () => json({ id: 'l1', short_url: null }, 201),
    })
    const { wrapper, titles, button, save } = await open()

    await button('New list')!.trigger('click')
    await wrapper.find('#save-new-list').setValue('  Reading ')
    await button('Create')!.trigger('click')
    await flushPromises()

    expect(bodies[calls.indexOf('POST /api/v2/lists/')]).toEqual({ title: 'Reading' })
    expect(titles()).toEqual(['Reading', 'List A'])
    await save()
    expect(calls.at(-1)).toBe('POST /api/v2/lists/N/links/')
  })

  it("narrows to a group's lists", async () => {
    site({
      [LISTS]: () => page([apiList('A'), apiList('B')]),
      [GROUPS]: () => page([apiGroup('G', { title: 'Team' })]),
      'GET /api/v2/groups/G/lists/': () =>
        json([apiList('B'), apiList('V', { permissions: ['view'] })]),
    })
    const { wrapper, titles } = await open()
    expect(wrapper.findAll('option').map((option) => option.text())).toEqual([
      'All my lists',
      'Group: Team',
    ])

    await wrapper.find('select').setValue('G')
    await flushPromises()
    expect(titles()).toEqual(['List B'])
  })

  it("doesn't offer a list that is full", async () => {
    site({ ...noGroups, [LISTS]: () => page([apiList('F', { link_count: 100 })]) })
    const { wrapper } = await open()

    expect(wrapper.find('input[type="radio"]').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Full (100 links)')
  })

  it('finds a list by name once there are many', async () => {
    const many = Array.from({ length: 8 }, (_, n) => apiList(`L${n}`, { title: `Topic ${n}` }))
    site({ ...noGroups, [LISTS]: () => page([...many, apiList('X', { title: 'Recipes' })]) })
    const { wrapper, titles } = await open()

    await wrapper.find('input[type="search"]').setValue('recip')
    expect(titles()).toEqual(['Recipes'])
    await wrapper.find('input[type="search"]').setValue('nothing like this')
    expect(wrapper.text()).toContain('No list matches.')
  })
})
