<script setup lang="ts">
// Opens a private edit link (/l/{code}/manage#t={token}): removes the token from the address
// bar at once, checks it, saves it in this browser and continues to the list as its owner.
import { mdiCalendarRemoveOutline, mdiKeyRemove, mdiLinkOff } from '@mdi/js'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { ApiError, errorMessage, verifyOwnership } from '../api'
import StatePanel from '../components/StatePanel.vue'
import { tokenFromHash } from '../composables/useEditLink'
import { useNotify } from '../composables/useNotify'
import { useOwnedLists } from '../composables/useOwnedLists'

const props = defineProps<{ code: string }>()
const router = useRouter()
const owned = useOwnedLists()
const notify = useNotify()

type State = 'checking' | 'missing' | 'rejected' | 'not-found' | 'expired' | 'error'
const state = ref<State>('checking')
const message = ref('')

onMounted(async () => {
  const token = tokenFromHash(window.location.hash)
  // Never leave the secret in the address bar, history entry or a screenshot.
  history.replaceState(history.state, '', window.location.pathname)
  if (!token) {
    // No token in the link, but this browser may already own the list.
    if (owned.tokenFor(props.code))
      return router.replace({ name: 'list', params: { code: props.code } })
    state.value = 'missing'
    return
  }
  try {
    const list = await verifyOwnership(props.code, token)
    owned.save({ code: props.code, token, title: list.title, expiresAt: list.expires_at ?? '' })
    notify.success('Editing unlocked on this device')
    router.replace({ name: 'list', params: { code: props.code } })
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403))
      state.value = 'rejected'
    else if (error instanceof ApiError && error.status === 404) state.value = 'not-found'
    else if (error instanceof ApiError && error.status === 410) state.value = 'expired'
    else {
      state.value = 'error'
      message.value = errorMessage(error)
    }
  }
})
</script>

<template>
  <div class="ll-content py-10">
    <div v-if="state === 'checking'" class="text-center py-16" aria-busy="true">
      <v-progress-circular indeterminate color="primary" size="48" class="mb-6" />
      <h1 class="text-headline-small">Opening your list…</h1>
    </div>
    <StatePanel
      v-else-if="state === 'rejected'"
      as="h1"
      tone="warning"
      :icon="mdiKeyRemove"
      title="This edit link no longer works"
      text="It was replaced by a newer edit link. Use the newest one you saved. You can still view the list."
    >
      <template #actions>
        <v-btn color="primary" :to="{ name: 'list', params: { code } }">View the list</v-btn>
      </template>
    </StatePanel>
    <StatePanel
      v-else-if="state === 'missing'"
      as="h1"
      tone="warning"
      :icon="mdiKeyRemove"
      title="This edit link is incomplete"
      text="The secret part after # is missing. Copy the whole edit link and try again."
    >
      <template #actions>
        <v-btn color="primary" :to="{ name: 'list', params: { code } }">View the list</v-btn>
      </template>
    </StatePanel>
    <StatePanel
      v-else-if="state === 'not-found'"
      as="h1"
      :icon="mdiLinkOff"
      title="This list doesn't exist"
      text="It may have been deleted."
    >
      <template #actions>
        <v-btn color="primary" :to="{ name: 'home', hash: '#create' }">Create a new list</v-btn>
      </template>
    </StatePanel>
    <StatePanel
      v-else-if="state === 'expired'"
      as="h1"
      tone="warning"
      :icon="mdiCalendarRemoveOutline"
      title="This list has expired"
      text="This list reached its end date, so it can no longer be opened."
    >
      <template #actions>
        <v-btn color="primary" :to="{ name: 'home', hash: '#create' }">Create a new list</v-btn>
      </template>
    </StatePanel>
    <StatePanel
      v-else
      as="h1"
      tone="error"
      :icon="mdiLinkOff"
      title="Couldn't open the list"
      :text="message"
    >
      <template #actions>
        <v-btn color="primary" @click="$router.go(0)">Try again</v-btn>
      </template>
    </StatePanel>
  </div>
</template>
