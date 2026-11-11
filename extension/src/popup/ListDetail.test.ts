import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { GroupSummary } from '../lib/lists'
import { getCachedLists, type ListSummary, saveConnection } from '../lib/storage'
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

  it('goes back, and reports a connection that is over', async () => {
    site({ [LINKS]: () => json({ detail: 'Sign in.' }, 401) })
    const { wrapper, button } = await open()
    expect(wrapper.emitted('disconnected')).toHaveLength(1)

    await button('‹ All lists')!.trigger('click')
    expect(wrapper.emitted('back')).toHaveLength(1)
  })
})
