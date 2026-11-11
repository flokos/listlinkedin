import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { GroupSummary } from '../lib/lists'
import { cacheLists, getCachedLists, type ListSummary, saveConnection } from '../lib/storage'
import { ADA, json } from '../test/fakeBrowser'
import { apiLink, apiList, listSummary, page, type Route, site } from '../test/site'
import ListDetail from './ListDetail.vue'

const LINKS = 'GET /api/v2/lists/A/links/'
const PATCH = 'PATCH /api/v2/lists/A/'
const twoLinks: Record<string, Route> = { [LINKS]: () => page([apiLink('1'), apiLink('2')]) }

const group = (code: string, extra: Partial<GroupSummary> = {}): GroupSummary => ({
  code,
  title: `Group ${code}`,
  url: `https://lists.example.test/g/${code}`,
  visibility: 'private',
  listCount: 1,
  canAddList: true,
  canEdit: true,
  canDelete: true,
  canSet: true,
  ...extra,
})

async function open(list: ListSummary = listSummary('A'), groups: GroupSummary[] = []) {
  const wrapper = mount(ListDetail, { attachTo: document.body, props: { list, groups } })
  await flushPromises()
  const button = (text: string) => wrapper.findAll('button').find((b) => b.text() === text)
  const note = () => wrapper.find('.ll-notice')
  return { wrapper, button, note }
}

function clipboard(works = true) {
  const written: string[] = []
  vi.stubGlobal('navigator', {
    clipboard: {
      writeText: vi.fn(async (text: string) => {
        if (!works) throw new Error('not allowed')
        written.push(text)
      }),
    },
  })
  return written
}

beforeEach(() => saveConnection(ADA))

describe('ListDetail', () => {
  it("shows the list's links, each opening its page in a new tab", async () => {
    site(twoLinks)
    const { wrapper } = await open(listSummary('A', { title: 'Reading', linkCount: 2 }))

    expect(wrapper.find('h2').text()).toBe('Reading')
    expect(wrapper.text()).toContain('2 links · Only people you add')
    const links = wrapper.findAll('.detail__links a')
    expect(links.map((link) => link.text())).toEqual(['Link 1', 'Link 2'])
    expect(links[0]!.attributes()).toMatchObject({
      href: 'https://example.com/1',
      target: '_blank',
      rel: 'noreferrer',
    })
    expect(wrapper.text()).toContain('example.com')
  })

  it('never makes a link of an address that is not a web address', async () => {
    site({
      [LINKS]: () => page([apiLink('1', { destination_url: 'javascript:alert(1)' })]),
    })
    const { wrapper } = await open()
    expect(wrapper.find('.detail__links a').exists()).toBe(false)
    expect(wrapper.find('.detail__links').text()).toContain('Link 1')
  })

  it("copies the list's link and says who can open it, without changing that", async () => {
    const written = clipboard()
    const { calls } = site(twoLinks)
    const { button, note } = await open()

    await button('Copy link')!.trigger('click')
    await flushPromises()

    expect(written).toEqual(['https://lists.example.test/l/A'])
    expect(note().text()).toBe('Link copied. Only people you add can open this link.')
    expect(calls).toEqual(['GET /api/v2/lists/A/links/?page_size=100&page=1'])
  })

  it("copies a link's short link", async () => {
    const written = clipboard()
    site(twoLinks)
    const { wrapper, note } = await open(listSummary('A', { visibility: 'public' }))

    await wrapper.find('[aria-label="Copy the short link of Link 2"]').trigger('click')
    await flushPromises()

    expect(written).toEqual(['https://lists.example.test/r/short-2'])
    expect(note().text()).toBe('Short link copied. Anyone can view this list, but not change it.')
  })

  it('shows the address to copy by hand when the browser refuses', async () => {
    clipboard(false)
    document.execCommand = vi.fn(() => false)
    site(twoLinks)
    const { button, note } = await open()
    await button('Copy link')!.trigger('click')
    await flushPromises()
    expect(note().attributes('role')).toBe('alert')
    expect(note().text()).toContain('https://lists.example.test/l/A')
  })

  it('changes who can open the list only when the user chooses and confirms', async () => {
    const { calls, bodies } = site({
      ...twoLinks,
      [PATCH]: () => json(apiList('A', { visibility: 'unlisted' })),
    })
    const { wrapper, button, note } = await open()
    const select = wrapper.find('#detail-visibility')

    expect((select.element as HTMLSelectElement).value).toBe('private')
    expect(wrapper.findAll('#detail-visibility option').map((option) => option.text())).toEqual([
      'Only people you add',
      'Anyone with the link',
      'Public',
    ])
    expect(button('Change')!.attributes('disabled')).toBeDefined()

    await select.setValue('unlisted')
    expect(calls).not.toContain(PATCH) // choosing is not yet changing
    await button('Change')!.trigger('click')
    await flushPromises()

    expect(bodies[calls.indexOf(PATCH)]).toEqual({ visibility: 'unlisted' })
    expect(wrapper.emitted('changed')![0]).toEqual([
      expect.objectContaining({ code: 'A', visibility: 'unlisted' }),
    ])
    expect(note().text()).toBe(
      'Changed. Anyone with this link can view the list, but not change it.',
    )
  })

  it("says why and changes nothing when the site won't", async () => {
    site({
      ...twoLinks,
      [PATCH]: () =>
        json({ visibility: ['Verify your email address to make a list public.'] }, 400),
    })
    const { wrapper, button, note } = await open()

    await wrapper.find('#detail-visibility').setValue('public')
    await button('Change')!.trigger('click')
    await flushPromises()

    expect(note().text()).toBe('Verify your email address to make a list public.')
    expect((wrapper.find('#detail-visibility').element as HTMLSelectElement).value).toBe('private')
    expect(wrapper.emitted('changed')).toBeUndefined()
    expect(await getCachedLists()).toBeNull()
  })

  it("offers no choice to someone who can't make it, and says who can open the list", async () => {
    site(twoLinks)
    const { wrapper } = await open(listSummary('A', { canSet: false, canEdit: false }))
    expect(wrapper.find('#detail-visibility').exists()).toBe(false)
    expect(wrapper.text()).toContain('Only people added to this list can open this link.')
  })

  it('adds the list to a group the account may add lists to', async () => {
    const { calls, bodies } = site({
      ...twoLinks,
      'POST /api/v2/groups/G/lists/': () => json(apiList('A'), 201),
    })
    const groups = [group('G', { title: 'Team' }), group('N', { canAddList: false })]
    const { wrapper, button, note } = await open(listSummary('A'), groups)

    expect(wrapper.findAll('#detail-group option').map((option) => option.text())).toEqual([
      'Choose a group',
      'Team',
    ])
    expect(button('Add')!.attributes('disabled')).toBeDefined()
    await wrapper.find('#detail-group').setValue('G')
    await button('Add')!.trigger('click')
    await flushPromises()

    expect(bodies[calls.indexOf('POST /api/v2/groups/G/lists/')]).toEqual({ list: 'A' })
    expect(note().text()).toBe('Added to the group “Team”.')
  })

  it("passes on the site's reason when a list can't be added to the group", async () => {
    site({
      ...twoLinks,
      'POST /api/v2/groups/G/lists/': () =>
        json({ detail: 'This list is already in the group.', code: 'duplicate_list' }, 409),
    })
    const { wrapper, button, note } = await open(listSummary('A'), [group('G')])
    await wrapper.find('#detail-group').setValue('G')
    await button('Add')!.trigger('click')
    await flushPromises()
    expect(note().text()).toBe('This list is already in the group.')
  })

  it('offers no group when there is none to add to', async () => {
    site(twoLinks)
    const { wrapper } = await open(listSummary('A'), [group('N', { canAddList: false })])
    expect(wrapper.find('#detail-group').exists()).toBe(false)
  })

  it('says so for a list without links, and when the links cannot be read', async () => {
    site({ [LINKS]: () => page([]) })
    expect((await open()).wrapper.text()).toContain('This list has no links yet.')

    site({ [LINKS]: () => json({ detail: 'Not found.' }, 404) })
    expect((await open()).wrapper.find('[role="alert"]').text()).toBe('Not found.')
  })

  describe('editing the links', () => {
    const REORDER = 'POST /api/v2/lists/A/reorder/'
    const three: Record<string, Route> = {
      [LINKS]: () => page([apiLink('1'), apiLink('2'), apiLink('3')]),
    }
    const titles = (wrapper: Awaited<ReturnType<typeof open>>['wrapper']) =>
      wrapper.findAll('.detail__link-title').map((title) => title.text())

    it('is offered only to who may edit the list, and only when asked for', async () => {
      site(three)
      const viewer = await open(listSummary('A', { canEdit: false }))
      expect(viewer.button('Edit links')).toBeUndefined()

      const { wrapper, button } = await open()
      expect(wrapper.find('.detail__move').exists()).toBe(false)
      await button('Edit links')!.trigger('click')
      expect(wrapper.findAll('.detail__move')).toHaveLength(6)
      // Nothing above the first, nothing below the last.
      expect(wrapper.find('[aria-label="Move Link 1 up"]').attributes('disabled')).toBeDefined()
      expect(wrapper.find('[aria-label="Move Link 3 down"]').attributes('disabled')).toBeDefined()
      await button('Done')!.trigger('click')
      expect(wrapper.find('.detail__move').exists()).toBe(false)
    })

    it('moves a link by one place and shows the order the site answers with', async () => {
      const { calls, bodies } = site({
        ...three,
        [REORDER]: () => json([apiLink('2'), apiLink('1'), apiLink('3')]),
      })
      const { wrapper, button, note } = await open()
      await button('Edit links')!.trigger('click')

      await wrapper.find('[aria-label="Move Link 2 up"]').trigger('click')
      await flushPromises()

      expect(bodies[calls.indexOf(REORDER)]).toEqual({ link: '2', to_index: 0 })
      expect(titles(wrapper)).toEqual(['Link 2', 'Link 1', 'Link 3'])
      expect(note().text()).toBe('“Link 2” is now 1 of 3.')
      // It reached the top: the keyboard is on the button that still does something.
      expect(document.activeElement?.getAttribute('aria-label')).toBe('Move Link 2 down')
    })

    it('moves a link that is dragged onto another to that place', async () => {
      const { calls, bodies } = site({
        ...three,
        [REORDER]: () => json([apiLink('2'), apiLink('3'), apiLink('1')]),
      })
      const { wrapper, button, note } = await open()
      const row = (id: string) => wrapper.find(`[data-link="${id}"]`)
      expect(row('1').attributes('draggable')).toBeUndefined() // not before "Edit links"
      await button('Edit links')!.trigger('click')
      expect(row('1').attributes('draggable')).toBe('true')

      const dataTransfer = { setData: vi.fn(), effectAllowed: '', dropEffect: '' }
      await row('1').trigger('dragstart', { dataTransfer })
      expect(dataTransfer.setData).toHaveBeenCalledWith('text/plain', 'Link 1') // Firefox needs data
      await row('3').trigger('dragover', { dataTransfer })
      expect(row('3').classes()).toContain('detail__link--over')
      await row('3').trigger('drop', { dataTransfer })
      await flushPromises()

      expect(bodies[calls.indexOf(REORDER)]).toEqual({ link: '1', to_index: 2 })
      expect(titles(wrapper)).toEqual(['Link 2', 'Link 3', 'Link 1'])
      expect(note().text()).toBe('“Link 1” is now 3 of 3.')
      expect(wrapper.find('.detail__link--over').exists()).toBe(false)
    })

    it('does nothing when a link is dropped on itself, or something else is dropped', async () => {
      const { calls } = site(three)
      const { wrapper, button } = await open()
      await button('Edit links')!.trigger('click')
      const row = wrapper.find('[data-link="2"]')
      const dataTransfer = { setData: vi.fn(), effectAllowed: '', dropEffect: '' }

      await row.trigger('drop', { dataTransfer }) // a file, a tab: not one of these rows
      await row.trigger('dragstart', { dataTransfer })
      await row.trigger('drop', { dataTransfer })
      await flushPromises()

      expect(calls.filter((call) => call.startsWith('POST'))).toEqual([])
    })

    it('reads the links again when a move fails', async () => {
      let reads = 0
      site({
        [LINKS]: () => page(reads++ ? [apiLink('3'), apiLink('1')] : [apiLink('1'), apiLink('3')]),
        [REORDER]: () => json({ detail: 'This link is no longer in the list.' }, 404),
      })
      const { wrapper, button, note } = await open()
      await button('Edit links')!.trigger('click')
      await wrapper.find('[aria-label="Move Link 1 down"]').trigger('click')
      await flushPromises()

      expect(note().attributes('role')).toBe('alert')
      expect(titles(wrapper)).toEqual(['Link 3', 'Link 1'])
    })

    it('removes a link only after it was asked about', async () => {
      const DELETE = 'DELETE /api/v2/lists/A/links/2/'
      const { calls } = site({ ...three, [DELETE]: () => new Response(null, { status: 204 }) })
      await cacheLists([listSummary('A', { linkCount: 3 })])
      const { wrapper, button, note } = await open(listSummary('A', { linkCount: 3 }))
      await button('Edit links')!.trigger('click')

      await wrapper.find('[aria-label="Remove Link 2…"]').trigger('click')
      await flushPromises()
      expect(calls).not.toContain(DELETE) // asked, not done
      expect(document.activeElement?.textContent?.trim()).toBe('Keep')

      await button('Keep')!.trigger('click')
      await flushPromises()
      expect(calls).not.toContain(DELETE)
      expect(titles(wrapper)).toEqual(['Link 1', 'Link 2', 'Link 3'])

      await wrapper.find('[aria-label="Remove Link 2…"]').trigger('click')
      await wrapper.find('[aria-label="Remove Link 2 from the list"]').trigger('click')
      await flushPromises()

      expect(calls).toContain(DELETE)
      expect(titles(wrapper)).toEqual(['Link 1', 'Link 3'])
      expect(note().text()).toContain('Removed “Link 2”.')
      expect(wrapper.emitted('changed')![0]).toEqual([expect.objectContaining({ linkCount: 2 })])
      expect((await getCachedLists())![0]!.linkCount).toBe(2)
    })

    it("says why and reads the links again when the site won't remove one", async () => {
      site({
        ...three,
        'DELETE /api/v2/lists/A/links/1/': () =>
          json({ detail: 'You can no longer change this list.' }, 403),
      })
      const { wrapper, button, note } = await open()
      await button('Edit links')!.trigger('click')
      await wrapper.find('[aria-label="Remove Link 1…"]').trigger('click')
      await wrapper.find('[aria-label="Remove Link 1 from the list"]').trigger('click')
      await flushPromises()

      expect(note().text()).toBe('You can no longer change this list.')
      expect(titles(wrapper)).toHaveLength(3)
      expect(wrapper.emitted('changed')).toBeUndefined()
    })
  })

  it('goes back, and reports a connection that is over', async () => {
    site({ [LINKS]: () => json({ detail: 'Sign in.' }, 401) })
    const { wrapper, button } = await open()
    expect(wrapper.emitted('disconnected')).toHaveLength(1)

    await button('‹ All lists')!.trigger('click')
    expect(wrapper.emitted('back')).toHaveLength(1)
  })
})
