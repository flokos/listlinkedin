import { computed, onScopeDispose, ref, shallowRef, watch, type Ref } from 'vue'

import * as api from '../api'
import {
  ApiError,
  revisionOf,
  type ListDetail,
  type ListInput,
  type SharedLink,
  type WriteOptions,
} from '../api'
import { useOwnedLists } from './useOwnedLists'
import { onUserChange, useSession } from './useSession'

export type ListStatus = 'loading' | 'ready' | 'not-found' | 'expired' | 'error'

// Last loaded state per list, so returning to a list shows it instantly while it refreshes.
// Dropped when the user signs out or changes: nobody is shown what the last one could see.
const cache = new Map<string, { list: ListDetail; links: SharedLink[] }>()
onUserChange(() => cache.clear())

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
      startPolling()
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

  /** Keeps the list's head revision current from a write's ETag. */
  function noteEtag(etag: string | null) {
    const head = revisionOf(etag)
    if (head !== undefined && list.value && list.value.head_revision !== head) {
      list.value = { ...list.value, head_revision: head }
    }
  }

  /**
   * Content writes are based on the version on screen (If-Match). If someone else changed the
   * list meanwhile, the server refuses (412) instead of overwriting: `act` then reloads, and
   * the form keeps what the user typed so they can check and save again.
   */
  const based = (): WriteOptions => ({ ifMatch: list.value?.head_revision, onEtag: noteEtag })

  /** Runs an editing action; a 401/403 with a saved edit link means it no longer works. */
  async function act<T>(action: (token: string | undefined) => Promise<T>): Promise<T> {
    try {
      return await action(token.value)
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        if (token.value) ownerRevoked.value = true
      }
      if (error instanceof ApiError && error.status === 412) void load()
      if (error instanceof ApiError && error.status === 410) status.value = 'expired'
      throw error
    }
  }

  async function change(changes: ListInput) {
    list.value = await act((t) => api.changeList(code.value, changes, t, based()))
    if (token.value && changes.title) owned.update(code.value, { title: changes.title })
    remember()
  }

  const rename = (title: string) => change({ title })

  async function addLink(input: api.LinkInput) {
    const link = await act((t) => api.createLink(code.value, input, t, based()))
    links.value = [...links.value, link] // appended, as on the server
    remember()
    startPolling() // its details are being fetched
    return link
  }

  async function editLink(id: string, input: api.LinkInput) {
    const link = await act((t) => api.changeLink(code.value, id, input, t, based()))
    links.value = links.value.map((l) => (l.id === id ? link : l))
    remember()
    startPolling() // a new URL: its details are being fetched
    return link
  }

  /** Fetch a link's page details again (editors; the server allows one per hour). */
  async function refreshMetadata(id: string) {
    await act(() => api.refreshLinkMetadata(code.value, id))
    refreshing.set(id, links.value.find((l) => l.id === id)?.fetched ?? null)
    startPolling()
  }

  // Page details (title, description, icon) are fetched in the background, so while a link
  // is pending, or was just refreshed, check again, a little later each time, for about a
  // minute. Only those links' metadata fields are merged in, so a drag or an edit in
  // progress is never overwritten.
  const POLL_DELAYS = [2000, 3000, 5000, 8000, 13000, 20000]
  const refreshing = new Map<string, SharedLink['fetched']>() // id -> details before it
  let pollTimer: ReturnType<typeof setTimeout> | undefined
  let pollStep = 0

  const waiting = (link: SharedLink) =>
    link.metadata_status === 'pending' || refreshing.has(link.id)

  function startPolling() {
    pollStep = 0
    schedulePoll()
  }

  function schedulePoll() {
    clearTimeout(pollTimer)
    if (status.value !== 'ready' || !links.value.some(waiting)) return
    if (pollStep >= POLL_DELAYS.length) {
      refreshing.clear()
      return
    }
    pollTimer = setTimeout(checkPending, POLL_DELAYS[pollStep++])
  }

  async function checkPending() {
    const listCode = code.value
    try {
      const page = await api.listLinks(listCode, token.value)
      if (listCode !== code.value) return
      const fresh = new Map(page.results.map((l) => [l.id, l]))
      links.value = links.value.map((link) => {
        const update = fresh.get(link.id)
        if (!update || !waiting(link)) return link
        if (
          refreshing.has(link.id) &&
          JSON.stringify(update.fetched) !== JSON.stringify(refreshing.get(link.id))
        ) {
          refreshing.delete(link.id) // the new details arrived
        }
        return {
          ...link,
          display: update.display,
          fetched: update.fetched,
          metadata_status: update.metadata_status,
        }
      })
      remember()
    } catch {
      // Offline or a hiccup: the next step tries again.
    }
    schedulePoll()
  }

  onScopeDispose(() => clearTimeout(pollTimer))

  /** Uploads (`file`) or removes (`null`) a link's own icon. Needs an account. */
  async function setLinkIcon(id: string, file: File | null) {
    let link: SharedLink
    if (file) {
      link = await act(() => api.uploadLinkIcon(code.value, id, file, based()))
    } else {
      await act(() => api.removeLinkIcon(code.value, id, based()))
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
      const order = await act((t) => api.reorderLinks(code.value, id, to, t, noteEtag))
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
    const link = await act(() => api.moveLinkToList(code.value, id, targetCode, noteEtag))
    links.value = links.value.filter((l) => l.id !== id)
    remember()
    cache.delete(targetCode)
    return link
  }

  async function removeLink(id: string) {
    await act((t) => api.removeLink(code.value, id, t, based()))
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

  /** Sets the list's image, or removes it with `null`. */
  async function setImage(file: File | null) {
    if (file) list.value = await act(() => api.uploadListImage(code.value, file))
    else {
      await act(() => api.removeListImage(code.value))
      if (list.value) list.value = { ...list.value, image_url: null }
    }
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
    refreshMetadata,
    setLinkIcon,
    moveLink,
    moveToList,
    removeLink,
    rotate,
    claim,
    leave,
    removeList,
    setImage,
    forget,
  }
}
