<script setup lang="ts">
// Opens the emailed verification link, /verify-email#key=… (fragment: never sent to the
// server). Verifying works whether or not this browser is signed in.
import { mdiAlertCircleOutline, mdiEmailCheckOutline, mdiLinkOff } from '@mdi/js'
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { ApiError, errorMessage, resendVerification, verifyEmail } from '../api'
import StatePanel from '../components/StatePanel.vue'
import { useNotify } from '../composables/useNotify'
import { useSession } from '../composables/useSession'
import { takeHashParam } from '../utils/url'

type State = 'verifying' | 'verified' | 'invalid' | 'error'

const route = useRoute()
const session = useSession()
const notify = useNotify()
let key = takeHashParam('key')
const state = ref<State>(key ? 'verifying' : 'invalid')
const message = ref('')
const resending = ref(false)

async function verify() {
  if (!key) return
  state.value = 'verifying'
  try {
    await verifyEmail(key)
    await session.refresh()
    state.value = 'verified'
  } catch (error) {
    if (error instanceof ApiError && error.status < 500) state.value = 'invalid'
    else {
      message.value = errorMessage(error)
      state.value = 'error'
    }
  }
}

async function resend() {
  const user = session.user.value
  if (!user) return
  resending.value = true
  try {
    const sent = await resendVerification(user.email)
    if (sent) notify.success(`We sent a new link to ${user.email}.`)
    else notify.info('We sent a link recently. Check your inbox, or try again in a few minutes.')
  } catch (error) {
    notify.error(errorMessage(error))
  } finally {
    resending.value = false
  }
}

onMounted(verify)
// Another link opened in a tab already on this page changes only the fragment.
watch(
  () => route.hash,
  () => {
    const value = takeHashParam('key')
    if (value) {
      key = value
      void verify()
    }
  },
)
</script>

<template>
  <div class="ll-content">
    <div v-if="state === 'verifying'" class="text-center py-16" aria-busy="true">
      <v-progress-circular indeterminate color="primary" size="48" class="mb-6" />
      <h1 class="text-headline-small">Verifying your email…</h1>
    </div>

    <StatePanel
      v-else-if="state === 'verified'"
      as="h1"
      :icon="mdiEmailCheckOutline"
      title="Your email is verified"
      text="Thanks for confirming your address."
    >
      <template #actions>
        <v-btn v-if="session.isSignedIn.value" color="primary" :to="{ name: 'account' }">
          Go to your account
        </v-btn>
        <v-btn v-else color="primary" :to="{ name: 'signin' }">Sign in</v-btn>
      </template>
    </StatePanel>

    <StatePanel
      v-else-if="state === 'invalid'"
      as="h1"
      tone="warning"
      :icon="mdiLinkOff"
      title="This link has expired or was already used"
      text="Verification links work once. If your email still isn't verified, ask for a new link."
    >
      <template #actions>
        <template v-if="session.user.value">
          <v-btn
            v-if="!session.user.value.email_verified"
            color="primary"
            :loading="resending"
            @click="resend"
          >
            Send a new link
          </v-btn>
          <v-btn variant="tonal" color="primary" :to="{ name: 'account' }">
            Go to your account
          </v-btn>
        </template>
        <v-btn v-else color="primary" :to="{ name: 'signin', query: { next: '/account' } }">
          Sign in
        </v-btn>
      </template>
    </StatePanel>

    <StatePanel
      v-else
      as="h1"
      tone="error"
      :icon="mdiAlertCircleOutline"
      title="Couldn't verify your email"
      :text="message"
    >
      <template #actions>
        <v-btn color="primary" @click="verify">Try again</v-btn>
      </template>
    </StatePanel>
  </div>
</template>
