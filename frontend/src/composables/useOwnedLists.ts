import { computed, reactive } from 'vue'

/** A list this browser can edit: its owner token plus enough to show it without a request. */
export interface OwnedList {
  code: string
  token: string
  title: string
  expiresAt: string
  savedAt: string
}

export const STORAGE_KEY = 'll:owned-lists'

function read(): Record<string, OwnedList> {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}')
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
    const valid: Record<string, OwnedList> = {}
    for (const [code, entry] of Object.entries(parsed as Record<string, Partial<OwnedList>>)) {
      if (entry && typeof entry.token === 'string' && typeof entry.code === 'string') {
        valid[code] = {
          code: entry.code,
          token: entry.token,
          title: entry.title ?? '',
          expiresAt: entry.expiresAt ?? '',
          savedAt: entry.savedAt ?? new Date(0).toISOString(),
        }
      }
    }
    return valid
  } catch {
    return {} // corrupt or unavailable storage: behave as if nothing is saved
  }
}

const state = reactive<{ lists: Record<string, OwnedList> }>({ lists: read() })

function persist() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.lists))
  } catch {
    // Private mode or full storage: keep working in memory for this session.
  }
}

// Keep tabs in sync: saving or forgetting a list in one tab updates the others.
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (event) => {
    if (event.key === STORAGE_KEY || event.key === null) state.lists = read()
  })
}

/**
 * Owner tokens saved in this browser (localStorage). Tokens never leave the browser except
 * as the Authorization header to this site's API.
 */
export function useOwnedLists() {
  const lists = computed(() =>
    Object.values(state.lists).sort((a, b) => b.savedAt.localeCompare(a.savedAt)),
  )

  return {
    lists,
    count: computed(() => lists.value.length),
    get: (code: string): OwnedList | undefined => state.lists[code],
    tokenFor: (code: string): string | undefined => state.lists[code]?.token,
    save(entry: Omit<OwnedList, 'savedAt'> & { savedAt?: string }) {
      state.lists[entry.code] = {
        ...entry,
        savedAt: entry.savedAt ?? state.lists[entry.code]?.savedAt ?? new Date().toISOString(),
      }
      persist()
    },
    update(code: string, changes: Partial<Omit<OwnedList, 'code'>>) {
      const current = state.lists[code]
      if (!current) return
      state.lists[code] = { ...current, ...changes }
      persist()
    },
    forget(code: string) {
      delete state.lists[code]
      persist()
    },
    /** Re-read storage (tests, or after another tab changed it). */
    reload() {
      state.lists = read()
    },
  }
}
