// Groups, changed from the popup: making one, renaming it, who can open it, the lists in it
// and their order, deleting it. A group never gives anyone a list they couldn't open before
// (invariant 5): putting a list in a group, or taking it out, changes nothing about the list.
import { asAccount } from './account'
import { type ApiGroup, type ApiList, type GroupSummary, groupSummary, summary } from './lists'
import type { ListSummary, Visibility } from './storage'

const group = (code: string, rest = '') => `/api/v2/groups/${encodeURIComponent(code)}/${rest}`

/** Makes a group that `visibility` says who can open: the user's answer in the form. */
export async function createGroup(title: string, visibility: Visibility): Promise<GroupSummary> {
  return groupSummary(
    await asAccount<ApiGroup>('/api/v2/groups/', { method: 'POST', body: { title, visibility } }),
  )
}

/** Renames a group, or changes who can open it. Answers with the group as the site has it. */
export async function changeGroup(
  code: string,
  changes: { title?: string; visibility?: Visibility },
): Promise<GroupSummary> {
  return groupSummary(await asAccount<ApiGroup>(group(code), { method: 'PATCH', body: changes }))
}

/** Deletes a group. Its lists stay as they are. */
export async function deleteGroup(code: string): Promise<void> {
  await asAccount<null>(group(code), { method: 'DELETE' })
}

/** Takes a list out of a group. The list itself is untouched. */
export async function takeOutOfGroup(code: string, list: string): Promise<void> {
  await asAccount<null>(group(code, `lists/${encodeURIComponent(list)}/`), { method: 'DELETE' })
}

/**
 * Moves a list to `toIndex` (0-based) among the lists the group shows this account, and
 * answers with them in their new order.
 */
export async function moveInGroup(
  code: string,
  list: string,
  toIndex: number,
): Promise<ListSummary[]> {
  const lists = await asAccount<ApiList[]>(group(code, 'reorder/'), {
    method: 'POST',
    body: { list, to_index: toIndex },
  })
  return lists.map(summary)
}
