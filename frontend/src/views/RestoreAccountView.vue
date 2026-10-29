<script setup lang="ts">
// Signing in to an account that is being deleted lands here (docs/v2/adr/ADR-016): within the
// 30 days it can be restored with everything it had, or left to be erased.
import { mdiAccountReactivateOutline, mdiLogout } from '@mdi/js'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { errorMessage } from '../api'
import StatePanel from '../components/StatePanel.vue'
import { useNotify } from '../composables/useNotify'
import { useSession } from '../composables/useSession'
import { useSignOut } from '../composables/useSignOut'
import { formatDate } from '../utils/time'

const session = useSession()
const router = useRouter()
const notify = useNotify()
const signOut = useSignOut()
const restoring = ref(false)

const erasedOn = computed(() => {
  const when = session.user.value?.deletion_scheduled_for
  return when ? formatDate(when) : ''
})

async function restore() {
  restoring.value = true
  try {
    await session.restoreAccount()
    notify.success('Welcome back! Your account and your lists are restored.')
    await router.replace({ name: 'saved-lists' })
  } catch (error) {
    notify.error(errorMessage(error))
  } finally {
    restoring.value = false
  }
}
</script>

<template>
  <div class="ll-content">
    <StatePanel
      as="h1"
      tone="warning"
      :icon="mdiAccountReactivateOutline"
      title="Your account is being deleted"
    >
      It will be erased on {{ erasedOn }}, together with the lists you own. Until then nobody else
      can see them. Restore your account to get everything back as it was.
      <template #actions>
        <v-btn color="primary" :loading="restoring" @click="restore">Restore my account</v-btn>
        <v-btn variant="text" :prepend-icon="mdiLogout" :disabled="restoring" @click="signOut()">
          Sign out
        </v-btn>
      </template>
    </StatePanel>
  </div>
</template>
