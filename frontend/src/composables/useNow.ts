import { onScopeDispose, ref } from 'vue'

/** The current time, refreshed every `intervalMs`, for relative labels like "in 3 days". */
export function useNow(intervalMs = 60_000) {
  const now = ref(Date.now())
  const id = setInterval(() => (now.value = Date.now()), intervalMs)
  onScopeDispose(() => clearInterval(id))
  return now
}
