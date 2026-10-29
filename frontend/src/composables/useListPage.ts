import { computed, ref, shallowRef, watch, type Ref } from 'vue'

import * as api from '../api'
import { ApiError, type ListDetail, type ListInput, type SharedLink } from '../api'
import { useOwnedLists } from './useOwnedLists'
import { useSession } from './useSession'

export type ListStatus = 'loading' | 'ready' | 'not-found' | 'expired' | 'error'

// Last loaded state per list, so returning to a list shows it instantly while it refreshes.
const cache = new Map<string, { list: ListDetail; links: SharedLink[] }>()

/**
 * Everything the list page needs: loading, what this user may do, and every editing action.
 * The server decides permissions (`list.permissions`). A legacy list's edit-link token, if
 * this browser has one, is sent along; account lists use the session. Actions throw
 * ApiError/NetworkError so the calling form can show field errors.
 */
export function useListPage(code: Ref<string>) {
  const owned = useOwnedLists()
  const session = useSession()

  const list = shallowRef<ListDetail>()
  const links = ref<SharedLink[]>([])
  const status = ref<ListStatus>('loading')
  const loadError = ref<unknown>()
  /** This browser's edit link no longer works (replaced elsewhere, or the list was claimed). */
  const ownerRevoked = ref(false)

  const token = computed(() => owned.tokenFor(code.value))
  const can = (permission: string) => Boolean(list.value?.permissions.includes(permission))
  const isOwner = computed(() => can('edit'))
  watch(token, () => (ownerRevoked.value = false))

  let controller: AbortController | undefined

  async function load() {
    controller?.abort()
    controller = new AbortController()
    const { signal } = controller
    const cached = cache.get(code.value)
    if (cached) {
      list.value = cached.list
      links.value = cached.links
      status.value = 'ready'
    } else {
      status.value = 'loading'
    }
    try {
      const [listData, page] = await Promise.all([
        api.getListDetail(code.value, token.value, signal),
        api.listLinks(code.value, token.value, signal),
      ])
      list.value = listData
      links.value = page.results
      status.value = 'ready'
      loadError.value = undefined
      remember()
      if (token.value) reconcileToken(listData)
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return
      cache.delete(code.value)
      loadError.value = error
      status.value =
        error instanceof ApiError && error.status === 404
          ? 'not-found'
          : error instanceof ApiError && error.status === 410
            ? 'expired'
            : 'error'
    }
  }

  /** Keeps the device's saved edit link in step with what the server says about it. */
  function reconcileToken(listData: ListDetail) {
    if (!listData.legacy && listData.my_role === 'owner') {
      owned.forget(code.value) // added to this account: the edit link is retired
    } else if (!listData.permissions.includes('edit')) {
      ownerRevoked.value = true
    } else {
      owned.update(code.value, { title: listData.title, expiresAt: listData.expires_at ?? '' })
    }
  }

  function remember() {
    if (list.value) cache.set(code.value, { list: list.value, links: [...links.value] })
  }

  /** Runs an editing action; a 401/403 with a saved edit link means it no longer works. */
  async function act<T>(action: (token: string | undefined) => Promise<T>): Promise<T> {
    try {
      return await action(token.value)
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        if (token.value) ownerRevoked.value = true
      }
      if (error instanceof ApiError && error.status === 410) status.value = 'expired'
      throw error
    }
  }

  async function change(changes: ListInput) {
    list.value = await act((t) => api.changeList(code.value, changes, t))
    if (token.value && changes.title) owned.update(code.value, { title: changes.title })
    remember()
  }

  const rename = (title: string) => change({ title })

  async function addLink(input: api.LinkInput) {
    const link = await act((t) => api.createLink(code.value, input, t))
    links.value = [...links.value, link] // appended, as on the server
    remember()
    return link
  }

  async function editLink(id: string, input: api.LinkInput) {
    const link = await act((t) => api.changeLink(code.value, id, input, t))
    links.value = links.value.map((l) => (l.id === id ? link : l))
    remember()
    return link
  }

  /** Uploads (`file`) or removes (`null`) a link's own icon. Needs an account. */
  async function setLinkIcon(id: string, file: File | null) {
    let link: SharedLink
    if (file) {
      link = await act(() => api.uploadLinkIcon(code.value, id, file))
    } else {
      await act(() => api.removeLinkIcon(code.value, id))
      const current = links.value.find((l) => l.id === id)!
      // The fetched icon, if any, shows again: reload the link's server view.
      link = (await api.listLinks(code.value, token.value)).results.find((l) => l.id === id) ?? {
        ...current,
        icon_url: null,
      }
    }
    links.value = links.value.map((l) => (l.id === id ? link : l))
    remember()
    return link
  }

  /**
   * Moves a link to `toIndex` in the stored order. The page shows the move at once; the
   * server applies it to the current order under the list's lock and answers with that
   * order, which replaces ours (it includes concurrent changes by others).
   */
  async function moveLink(id: string, toIndex: number) {
    const before = links.value
    const from = before.findIndex((l) => l.id === id)
    if (from < 0) return
    const to = Math.max(0, Math.min(toIndex, before.length - 1))
    if (from === to) return
    const next = [...before]
    next.splice(to, 0, ...next.splice(from, 1))
    links.value = next
    const seq = ++moveSeq
    try {
      const order = await act((t) => api.reorderLinks(code.value, id, to, t))
      // Quick successive moves: only the latest answer describes the order on screen.
      if (seq === moveSeq) links.value = order
      remember()
    } catch (error) {
      if (seq === moveSeq) void load() // our guess is wrong: show the server's order
      throw error
    }
  }
  let moveSeq = 0

  /** Moves a link to another list (copied there with a new short link, deleted here). */
  async function moveToList(id: string, targetCode: string) {
    const link = await act(() => api.moveLinkToList(code.value, id, targetCode))
    links.value = links.value.filter((l) => l.id !== id)
    remember()
    cache.delete(targetCode)
    return link
  }

  async function removeLink(id: string) {
    await act((t) => api.removeLink(code.value, id, t))
    links.value = links.value.filter((l) => l.id !== id)
    remember()
  }

  /** Issues a new edit link for a legacy list; the old one stops working. */
  async function rotate() {
    const { owner_token } = await act((t) => api.replaceToken(code.value, t!))
    owned.update(code.value, { token: owner_token })
    return owner_token
  }

  /** Adds this legacy list to the signed-in account. Its edit link stops working. */
  async function claim() {
    const current = token.value
    if (!current) {
      throw new ApiError(403, { detail: 'This browser has no edit link for this list.' })
    }
    list.value = await api.claimList(code.value, current)
    owned.forget(code.value)
    remember()
  }

  async function removeList() {
    await act((t) => api.removeList(code.value, t))
    cache.delete(code.value)
    owned.forget(code.value)
  }

  /** Leaves a list you were added to (removes your own membership). */
  async function leave() {
    const me = session.user.value?.id
    if (!me) throw new ApiError(401, { detail: 'Sign in to leave this list.' })
    await api.removeMember(code.value, me)
    cache.delete(code.value)
  }

  function forget() {
    owned.forget(code.value)
    ownerRevoked.value = false
    void load()
  }

  // Reload when the list or the signed-in user changes: both change what you may do.
  watch(
    [code, () => session.user.value?.id],
    () => {
      ownerRevoked.value = false
      void load()
    },
    { immediate: true },
  )

  return {
    list,
    links,
    status,
    loadError,
    isOwner,
    ownerRevoked,
    token,
    can,
    load,
    change,
    rename,
    addLink,
    editLink,
    setLinkIcon,
    moveLink,
    moveToList,
    removeLink,
    rotate,
    claim,
    leave,
    removeList,
    forget,
  }
}
