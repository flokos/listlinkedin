// The signed-in user, shared by the whole app: header, route guards and account pages.
// The server decides; this only mirrors GET /api/v2/session/ and refreshes it after changes.
import { computed, reactive } from 'vue'

import * as api from '../api'
import type { SessionUser } from '../api'

type Status = 'unknown' | 'ready' | 'error'
const state = reactive<{ user: SessionUser | null; status: Status }>({
  user: null,
  status: 'unknown',
})
let loading: Promise<void> | undefined

// Run when the signed-in user goes away or changes, so what they could see is dropped from
// memory (ASVS V14.3.1): the list page's cache, for example.
const userChangeListeners = new Set<() => void>()

/** Calls `fn` whenever the signed-in user signs out or another one signs in. */
export function onUserChange(fn: () => void): void {
  userChangeListeners.add(fn)
}

function setUser(user: SessionUser | null) {
  const changed = (state.user?.id ?? null) !== (user?.id ?? null)
  state.user = user
  if (changed) for (const listener of userChangeListeners) listener()
}

/**
 * Loads the session once, or again with `force`. Never throws: if the server can't be
 * reached the app behaves as signed out, and the next action shows the network error.
 */
export function loadSession(force = false): Promise<void> {
  if (!force && state.status === 'ready') return Promise.resolve()
  if (!loading || force) {
    const current = api.getSession().then(
      (user) => {
        setUser(user)
        state.status = 'ready'
      },
      () => {
        setUser(null)
        state.status = 'error'
      },
    )
    loading = current
    void current.finally(() => {
      if (loading === current) loading = undefined
    })
  }
  return loading
}

/** The signed-in user right now, for route guards. Call `loadSession()` first. */
export const currentUser = (): SessionUser | null => state.user

/** The signed-in account is being deleted: the only thing it can do is restore or sign out. */
export const deletionPending = (): boolean => Boolean(state.user?.deletion_scheduled_for)

/** Whether the session has been checked already (so guards can decide without waiting). */
export const sessionKnown = (): boolean => state.status !== 'unknown'

export function useSession() {
  return {
    user: computed(() => state.user),
    isSignedIn: computed(() => state.user !== null),
    /** False until the first session check has finished. */
    ready: computed(() => state.status !== 'unknown'),
    refresh: () => loadSession(true),

    async signIn(email: string, password: string) {
      await api.signIn(email, password)
      await loadSession(true)
    },
    async signUp(email: string, password: string) {
      await api.signUp(email, password)
      await loadSession(true)
    },
    async signOut() {
      await api.signOut()
      setUser(null)
      state.status = 'ready'
    },
    /** Undoes deleting the account (within the grace period). */
    async restoreAccount() {
      state.user = await api.restoreAccount()
    },
    async updateDisplayName(displayName: string) {
      state.user = await api.updateMe({ display_name: displayName })
    },
    /** The server says the session ended (401 elsewhere): reflect it without a request. */
    markSignedOut() {
      setUser(null)
      state.status = 'ready'
    },
  }
}
