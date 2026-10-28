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

/**
 * Loads the session once, or again with `force`. Never throws: if the server can't be
 * reached the app behaves as signed out, and the next action shows the network error.
 */
export function loadSession(force = false): Promise<void> {
  if (!force && state.status === 'ready') return Promise.resolve()
  if (!loading || force) {
    const current = api.getSession().then(
      (user) => {
        state.user = user
        state.status = 'ready'
      },
      () => {
        state.user = null
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
      state.user = null
      state.status = 'ready'
    },
    async updateDisplayName(displayName: string) {
      state.user = await api.updateMe({ display_name: displayName })
    },
    /** The server says the session ended (401 elsewhere): reflect it without a request. */
    markSignedOut() {
      state.user = null
      state.status = 'ready'
    },
  }
}
