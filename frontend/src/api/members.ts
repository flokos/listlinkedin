// People a list is shared with: /api/v2/lists/{code}/members/ (docs/v2/09-API-DESIGN.md#lists).
// Session only: legacy (edit-link) lists have no members.
import { request } from './client'
import type { Page } from './lists'

export type MemberRole = 'editor' | 'viewer'

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
const members = (code: string) => `/api/v2/lists/${enc(code)}/members/`

export const listMembers = (code: string, signal?: AbortSignal) =>
  request<Page<Member>>(`${members(code)}?page_size=100`, { signal })

export const addMember = (code: string, email: string, role: MemberRole) =>
  request<Member>(members(code), { method: 'POST', body: { email, role } })

export const changeMember = (code: string, userId: string, role: MemberRole) =>
  request<Member>(`${members(code)}${enc(userId)}/`, { method: 'PATCH', body: { role } })

/** Removes someone (owner), or leaves the list (your own user id). */
export const removeMember = (code: string, userId: string) =>
  request<null>(`${members(code)}${enc(userId)}/`, { method: 'DELETE' })
