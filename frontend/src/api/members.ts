// People a list or group is shared with: /api/v2/{lists,groups}/{code}/members/
// (docs/v2/09-API-DESIGN.md#lists). Session only: legacy (edit-link) lists have no members.
import { request } from './client'
import type { Page } from './lists'

export type MemberRole = 'editor' | 'viewer'
/** What the people are added to. Groups have the same members API as lists. */
export type MemberKind = 'list' | 'group'

export interface Member {
  user_id: string
  display_name: string
  /** Enough of the address to tell people apart, e.g. `b…@example.com`. */
  email_hint: string
  role: MemberRole
  added_at: string
  is_you: boolean
}

const enc = encodeURIComponent
const members = (code: string, kind: MemberKind) =>
  `/api/v2/${kind === 'group' ? 'groups' : 'lists'}/${enc(code)}/members/`

export const listMembers = (code: string, kind: MemberKind = 'list') =>
  request<Page<Member>>(`${members(code, kind)}?page_size=100`)

export const addMember = (
  code: string,
  email: string,
  role: MemberRole,
  kind: MemberKind = 'list',
) => request<Member>(members(code, kind), { method: 'POST', body: { email, role } })

export const changeMember = (
  code: string,
  userId: string,
  role: MemberRole,
  kind: MemberKind = 'list',
) => request<Member>(`${members(code, kind)}${enc(userId)}/`, { method: 'PATCH', body: { role } })

/** Removes someone (owner), or leaves (your own user id). */
export const removeMember = (code: string, userId: string, kind: MemberKind = 'list') =>
  request<null>(`${members(code, kind)}${enc(userId)}/`, { method: 'DELETE' })
