import { computed, ref } from 'vue'
import { type LocationQuery, useRoute, useRouter } from 'vue-router'

/**
 * A dialog that is open while the address has `?dialog={name}`, so the browser's Back button
 * closes it and a link can open it. Closing goes Back once when opening it added the history
 * entry; opened from a link, it replaces the address instead (Back would leave the page).
 * It reads as closed as soon as it is closed, before the navigation ends: otherwise the dialog
 * sees itself still open, closes again (a second Back) or opens again.
 */
export function useQueryDialog(name: string, allowed: () => boolean = () => true) {
  const route = useRoute()
  const router = useRouter()
  const closing = ref(false)

  return computed({
    get: () => route.query.dialog === name && !closing.value && allowed(),
    set(open: boolean) {
      if (closing.value) return
      if (open) {
        void router.push({ query: { ...route.query, dialog: name } })
        return
      }
      if (route.query.dialog !== name) return
      const rest: LocationQuery = { ...route.query }
      delete rest.dialog
      closing.value = true
      const stop = router.afterEach(() => {
        closing.value = false
        stop()
      })
      const back = router.options.history.state.back
      if (back === router.resolve({ query: rest }).fullPath) router.back()
      else void router.replace({ query: rest })
    },
  })
}
