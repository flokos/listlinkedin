import { computed, ref, shallowRef, watch, type Ref } from 'vue'

import * as api from '../api'
import { ApiError, type SharedLink, type SharedList } from '../api'
import { useOwnedLists } from './useOwnedLists'

export type ListStatus = 'loading' | 'ready' | 'not-found' | 'expired' | 'error'

// Last loaded state per list, so returning to a list shows it instantly while it refreshes.
const cache = new Map<string, { list: SharedList; links: SharedLink[] }>()

/**
 * Everything the list page needs: loading, owner mode, and every owner action. Actions
 * throw ApiError/NetworkError so the calling form can show field errors; they also keep
 * local state and the browser's saved-list entry in sync.
 */
export function useListPage(code: Ref<string>) {
  const owned = useOwnedLists()

  const list = shallowRef<SharedList>()
  const links = ref<SharedLink[]>([])
  const status = ref<ListStatus>('loading')
  const loadError = ref<unknown>()
  /** The saved token was rejected (rotated elsewhere): edit access is gone. */
  const ownerRevoked = ref(false)

  const token = computed(() => owned.tokenFor(code.value))
  const isOwner = computed(() => Boolean(token.value) && !ownerRevoked.value)
  // A new token (pasted edit link, restored backup, another tab) gets a fresh chance.
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
        api.getList(code.value, signal),
        api.getLinks(code.value, signal),
      ])
      list.value = listData
      links.value = page.results
      status.value = 'ready'
      loadError.value = undefined
      remember()
      // Keep the saved entry's title and expiry fresh for the Saved lists page.
      if (token.value)
        owned.update(code.value, { title: listData.title, expiresAt: listData.expires_at })
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

  function remember() {
    if (list.value) cache.set(code.value, { list: list.value, links: [...links.value] })
  }

  /** Runs an owner action; a 401/403 means the saved token no longer works. */
  async function asOwner<T>(action: (token: string) => Promise<T>): Promise<T> {
    if (!token.value)
      throw new ApiError(401, { detail: 'You need the edit link to change this list.' })
    try {
      return await action(token.value)
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        ownerRevoked.value = true
      }
      if (error instanceof ApiError && error.status === 410) status.value = 'expired'
      throw error
    }
  }

  async function rename(title: string) {
    list.value = await asOwner((t) => api.updateList(code.value, t, title))
    owned.update(code.value, { title })
    remember()
  }

  async function addLink(input: api.LinkInput) {
    const link = await asOwner((t) => api.addLink(code.value, t, input))
    links.value = [link, ...links.value]
    remember()
    return link
  }

  async function editLink(id: string, input: api.LinkInput) {
    const link = await asOwner((t) => api.updateLink(code.value, t, id, input))
    links.value = links.value.map((l) => (l.id === id ? link : l))
    remember()
    return link
  }

  async function removeLink(id: string) {
    await asOwner((t) => api.deleteLink(code.value, t, id))
    links.value = links.value.filter((l) => l.id !== id)
    remember()
  }

  /** Issues a new edit link; the old one stops working. Returns the new token. */
  async function rotate() {
    const { owner_token } = await asOwner((t) => api.rotateToken(code.value, t))
    owned.update(code.value, { token: owner_token })
    return owner_token
  }

  async function removeList() {
    await asOwner((t) => api.deleteList(code.value, t))
    cache.delete(code.value)
    owned.forget(code.value)
  }

  function forget() {
    owned.forget(code.value)
    ownerRevoked.value = false
  }

  watch(
    code,
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
    load,
    rename,
    addLink,
    editLink,
    removeLink,
    rotate,
    removeList,
    forget,
  }
}
