import { useRoute, useRouter } from 'vue-router'

import { errorMessage } from '../api'
import { useNotify } from './useNotify'
import { useSession } from './useSession'

/** Signs out, confirms it, and leaves pages that need an account. */
export function useSignOut() {
  const route = useRoute()
  const router = useRouter()
  const notify = useNotify()
  const session = useSession()

  return async function signOut(): Promise<void> {
    try {
      await session.signOut()
    } catch (error) {
      notify.error(errorMessage(error))
      return
    }
    notify.info('Signed out')
    if (route.meta.requiresAuth) await router.replace({ name: 'home' })
  }
}
