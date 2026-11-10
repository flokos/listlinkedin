<script setup lang="ts">
// The browser extension opens /connect-browser?challenge=…&name=… to be let in to the account
// (docs/v2/adr/ADR-020). Signing in comes first (the route guard); then this page asks the
// extension whether it really started this, the user approves, and the one-time code goes to
// the extension through the page itself (utils/extensionBridge), never through a URL.
import {
  mdiAlertCircleOutline,
  mdiPuzzleCheckOutline,
  mdiPuzzleOutline,
  mdiPuzzleRemoveOutline,
} from '@mdi/js'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiError, approveBrowser, errorMessage } from '../api'
import AuthPanel from '../components/AuthPanel.vue'
import StatePanel from '../components/StatePanel.vue'
import { useSession } from '../composables/useSession'
import { findExtension, sendCode } from '../utils/extensionBridge'

/**
 * - `no-extension`: nothing answered, so this browser has no extension to connect.
 * - `not-started`: the extension is here but didn't open this page: someone else's link.
 */
type State = 'checking' | 'no-extension' | 'not-started' | 'ready' | 'connected' | 'failed'

const route = useRoute()
const router = useRouter()
const session = useSession()

const one = (value: unknown) => (typeof value === 'string' ? value : '')
// PKCE's S256 challenge: 43 base64url characters. Anything else didn't come from the extension.
const challenge = /^[A-Za-z0-9_-]{43}$/.test(one(route.query.challenge))
  ? one(route.query.challenge)
  : null
/** What the extension calls this browser: a label, shown as plain text. */
const name = computed(
  () => one(route.query.name).replace(/\s+/g, ' ').trim().slice(0, 80) || 'This browser',
)

const state = ref<State>(challenge ? 'checking' : 'no-extension')
const connecting = ref(false)
const message = ref('')
/** Ten browsers are connected already: the way on is the account page. */
const full = ref(false)

onMounted(async () => {
  if (!challenge) return
  const started = await findExtension(challenge)
  state.value = started === null ? 'no-extension' : started ? 'ready' : 'not-started'
})

async function connect() {
  if (!challenge) return
  connecting.value = true
  try {
    const { code } = await approveBrowser(challenge, name.value)
    await sendCode(challenge, code)
    state.value = 'connected'
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      // Signed out meanwhile (another tab, an expired session): sign in and come back.
      session.markSignedOut()
      await router.replace({ name: 'signin', query: { next: route.fullPath } })
      return
    }
    full.value = error instanceof ApiError && error.code === 'too_many_browsers'
    message.value = error instanceof ApiError ? errorMessage(error) : (error as Error).message
    state.value = 'failed'
  } finally {
    connecting.value = false
  }
}
</script>

<template>
  <div class="ll-content">
    <div v-if="state === 'checking'" class="text-center py-16" aria-busy="true">
      <v-progress-circular indeterminate color="primary" size="48" class="mb-6" />
      <h1 class="text-headline-small">Looking for the extension…</h1>
    </div>

    <AuthPanel
      v-else-if="state === 'ready'"
      title="Connect this browser?"
      text="The listlinkedin extension wants to stay signed in to your account."
    >
      <dl class="ll-connect__facts text-body-large mb-5">
        <dt class="text-label-large text-medium-emphasis">Browser</dt>
        <dd class="mb-3">{{ name }}</dd>
        <dt class="text-label-large text-medium-emphasis">Account</dt>
        <dd>{{ session.user.value?.email }}</dd>
      </dl>
      <p class="text-body-medium text-medium-emphasis mb-6">
        The extension will be able to do what you can do when you are signed in: see and change your
        lists, groups and account. You can disconnect it at any time under Your account.
      </p>
      <div class="d-flex flex-wrap ga-3">
        <v-btn color="primary" size="large" :loading="connecting" @click="connect">Connect</v-btn>
        <v-btn variant="text" size="large" :disabled="connecting" :to="{ name: 'home' }">
          Cancel
        </v-btn>
      </div>
    </AuthPanel>

    <StatePanel
      v-else-if="state === 'connected'"
      as="h1"
      :icon="mdiPuzzleCheckOutline"
      title="This browser is connected"
    >
      {{ name }} now saves pages to your lists from the extension. You can close this tab.
      <template #actions>
        <v-btn color="primary" :to="{ name: 'saved-lists' }">Go to my lists</v-btn>
        <v-btn variant="tonal" color="primary" :to="{ name: 'account' }">Connected browsers</v-btn>
      </template>
    </StatePanel>

    <StatePanel
      v-else-if="state === 'not-started'"
      as="h1"
      tone="warning"
      :icon="mdiPuzzleRemoveOutline"
      title="This request didn't come from your extension"
      text="Someone may have sent you this link. Nothing was connected. To connect this browser, open the listlinkedin extension and choose Connect."
    >
      <template #actions>
        <v-btn color="primary" :to="{ name: 'home' }">Go to listlinkedin</v-btn>
      </template>
    </StatePanel>

    <StatePanel
      v-else-if="state === 'no-extension'"
      as="h1"
      :icon="mdiPuzzleOutline"
      title="Open this page from the extension"
      text="This page connects the listlinkedin browser extension to your account. Install the extension in this browser, then choose Connect in it."
    >
      <template #actions>
        <v-btn color="primary" :to="{ name: 'home' }">Go to listlinkedin</v-btn>
      </template>
    </StatePanel>

    <StatePanel
      v-else
      as="h1"
      tone="error"
      :icon="mdiAlertCircleOutline"
      title="This browser wasn't connected"
      :text="message"
    >
      <template #actions>
        <v-btn v-if="full" color="primary" :to="{ name: 'account' }">Connected browsers</v-btn>
        <v-btn v-else color="primary" :loading="connecting" @click="connect">Try again</v-btn>
      </template>
    </StatePanel>
  </div>
</template>

<style scoped>
.ll-connect__facts dd {
  overflow-wrap: anywhere;
}
</style>
