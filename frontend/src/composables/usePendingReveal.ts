// Hands the "save your edit link" step from the create form to the list page it navigates
// to. Only the list code is kept, in sessionStorage, so a reload before the user confirms
// shows the step again; the token itself is already saved by useOwnedLists.

const KEY = 'll:pending-reveal'
/** Fallback when sessionStorage is unavailable (private mode in some browsers). */
let memory: string | null = null

function read(): string | null {
  try {
    return sessionStorage.getItem(KEY)
  } catch {
    return null
  }
}

export function usePendingReveal() {
  return {
    set(code: string) {
      try {
        sessionStorage.setItem(KEY, code)
      } catch {
        // Storage unavailable: the step still shows once, just not after a reload.
      }
      memory = code
    },
    /** Whether the edit link for `code` still has to be acknowledged. */
    isPending: (code: string) => (read() ?? memory) === code,
    /** Call once the user confirmed they saved the edit link. */
    clear() {
      memory = null
      try {
        sessionStorage.removeItem(KEY)
      } catch {
        // ignore
      }
    },
  }
}
