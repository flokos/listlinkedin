import { shallowRef } from 'vue'

// Hands the "save your edit link" step from the create form to the list page it navigates
// to. In memory only: after a reload the token is still saved in the browser and the
// owner can show the edit link again from the list's menu.
const pending = shallowRef<{ code: string; token: string } | null>(null)

export function usePendingReveal() {
  return {
    set: (code: string, token: string) => (pending.value = { code, token }),
    /** Returns and clears the pending reveal for `code`, if any. */
    take(code: string) {
      const value = pending.value
      if (value?.code !== code) return null
      pending.value = null
      return value
    },
  }
}
