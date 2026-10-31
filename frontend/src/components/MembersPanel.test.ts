import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createVuetify } from 'vuetify'

const api = vi.hoisted(() => ({
  listMembers: vi.fn(),
  addMember: vi.fn(),
  changeMember: vi.fn(),
  removeMember: vi.fn(),
}))
vi.mock('../api', async (original) => ({ ...(await original<typeof import('../api')>()), ...api }))

import { ApiError, type Member } from '../api'
import MembersPanel from './MembersPanel.vue'

const vuetify = createVuetify()
const bob: Member = {
  user_id: 'b',
  display_name: 'Bob',
  email_hint: 'b…@example.com',
  role: 'viewer',
  added_at: '2026-10-29T00:00:00Z',
  is_you: false,
}

function mountPanel(props: Partial<InstanceType<typeof MembersPanel>['$props']> = {}) {
  return mount(MembersPanel, {
    props: {
      code: 'CODE',
      ownerName: 'Alice',
      youAreOwner: true,
      canManage: true,
      emailVerified: true,
      ...props,
    },
    global: { plugins: [vuetify] },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  api.listMembers.mockResolvedValue({ count: 1, next: null, previous: null, results: [bob] })
})

describe('MembersPanel', () => {
  it('lists the owner first, then the people on the list', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    expect(api.listMembers).toHaveBeenCalledWith('CODE', 'list')
    const items = wrapper.findAll('.v-list-item').map((item) => item.text())
    expect(items[0]).toContain('You')
    expect(items[0]).toContain('Owner')
    expect(items[1]).toContain('Bob')
    expect(items[1]).toContain('b…@example.com')
  })

  it('adds a person by email with the chosen permission', async () => {
    const carol = { ...bob, user_id: 'c', display_name: 'Carol', email_hint: 'c…@example.com' }
    api.addMember.mockResolvedValue(carol)
    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.find('input[type="email"]').setValue('  carol@example.com ')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(api.addMember).toHaveBeenCalledWith('CODE', 'carol@example.com', 'viewer', 'list')
    expect(wrapper.text()).toContain('Carol')
  })

  it('shows why someone could not be added under the email field', async () => {
    api.addMember.mockRejectedValue(new ApiError(400, { email: ["We couldn't add this person."] }))
    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.find('input[type="email"]').setValue('nobody@example.com')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain("We couldn't add this person.")
  })

  it('asks the owner to verify their email before adding people', async () => {
    const wrapper = mountPanel({ emailVerified: false })
    await flushPromises()
    expect(wrapper.text()).toContain('Verify your email address')
    expect(wrapper.find('input[type="email"]').attributes('disabled')).toBeDefined()
  })

  it('shows editors who has access, without controls', async () => {
    const wrapper = mountPanel({ canManage: false, youAreOwner: false })
    await flushPromises()
    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.find('[aria-label="Remove Bob"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('Can view')
  })
})
