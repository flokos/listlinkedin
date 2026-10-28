<script setup lang="ts">
// /reset-password asks for an email address. The emailed link comes back here as
// /reset-password#key=… (fragment: never sent to the server), to choose a new password.
import { mdiEmailFastOutline, mdiLinkOff, mdiLockCheckOutline } from '@mdi/js'
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { ApiError, checkPasswordResetKey, requestPasswordReset, resetPassword } from '../api'
import AuthPanel from '../components/AuthPanel.vue'
import PasswordField from '../components/PasswordField.vue'
import StatePanel from '../components/StatePanel.vue'
import { useSession } from '../composables/useSession'
import { formErrors, noErrors } from '../utils/forms'
import { takeHashParam } from '../utils/url'

type State = 'request' | 'sent' | 'checking' | 'choose' | 'invalid' | 'done'

const route = useRoute()
const session = useSession()
let key = takeHashParam('key')
const state = ref<State>(key ? 'checking' : 'request')

const email = ref('')
const sentTo = ref('')
const password = ref('')
const FIELDS = ['email', 'password'] as const
const errors = ref(noErrors(FIELDS))
const busy = ref(false)

async function checkKey() {
  if (!key) return
  state.value = 'checking'
  errors.value = noErrors(FIELDS)
  try {
    await checkPasswordResetKey(key)
    state.value = 'choose'
  } catch (error) {
    if (error instanceof ApiError && error.status < 500) state.value = 'invalid'
    else {
      state.value = 'request'
      errors.value = formErrors(error, FIELDS)
    }
  }
}

onMounted(checkKey)
// A link opened in a tab that already shows this page changes only the fragment, which
// doesn't remount the page: pick up the new key.
watch(
  () => route.hash,
  () => {
    const value = takeHashParam('key')
    if (value) {
      key = value
      void checkKey()
    }
  },
)

async function onRequest() {
  errors.value = noErrors(FIELDS)
  const value = email.value.trim()
  if (!value) {
    errors.value.fields.email = ['Enter your email address.']
    return
  }
  busy.value = true
  try {
    await requestPasswordReset(value)
    sentTo.value = value
    state.value = 'sent'
  } catch (error) {
    errors.value = formErrors(error, FIELDS)
  } finally {
    busy.value = false
  }
}

async function onChoose() {
  errors.value = noErrors(FIELDS)
  if (!password.value) {
    errors.value.fields.password = ['Choose a new password.']
    return
  }
  busy.value = true
  try {
    await resetPassword(key!, password.value)
    await session.refresh() // a reset ends every session, including this one
    state.value = 'done'
  } catch (error) {
    if (error instanceof ApiError && error.fieldErrors.key) state.value = 'invalid'
    else errors.value = formErrors(error, FIELDS)
  } finally {
    busy.value = false
  }
}

function startOver() {
  errors.value = noErrors(FIELDS)
  state.value = 'request'
}
</script>

<template>
  <div v-if="state === 'checking'" class="ll-content text-center py-16" aria-busy="true">
    <v-progress-circular indeterminate color="primary" size="48" class="mb-6" />
    <h1 class="text-headline-small">Checking your link…</h1>
  </div>

  <AuthPanel
    v-else-if="state === 'request'"
    title="Reset your password"
    text="Enter the email address of your account. We'll send you a link to choose a new password."
  >
    <v-alert v-if="errors.form" type="error" class="mb-4" :text="errors.form" />
    <v-form class="d-flex flex-column ga-4" novalidate @submit.prevent="onRequest">
      <v-text-field
        v-model="email"
        label="Email"
        type="email"
        autocomplete="email"
        :error-messages="errors.fields.email"
        hide-details="auto"
      />
      <v-btn type="submit" color="primary" size="large" block :loading="busy">
        Send reset link
      </v-btn>
    </v-form>
    <template #footer>
      <router-link :to="{ name: 'signin' }">Back to sign in</router-link>
    </template>
  </AuthPanel>

  <div v-else-if="state === 'sent'" class="ll-content">
    <StatePanel
      as="h1"
      :icon="mdiEmailFastOutline"
      title="Check your inbox"
      :text="`If an account exists for ${sentTo}, we've sent it a link to choose a new password. The link works once.`"
    >
      <template #actions>
        <v-btn color="primary" :to="{ name: 'signin' }">Back to sign in</v-btn>
      </template>
    </StatePanel>
  </div>

  <AuthPanel
    v-else-if="state === 'choose'"
    title="Choose a new password"
    text="You'll be signed out everywhere, then you can sign in with the new password."
  >
    <v-alert v-if="errors.form" type="error" class="mb-4" :text="errors.form" />
    <v-form class="d-flex flex-column ga-4" novalidate @submit.prevent="onChoose">
      <PasswordField
        v-model="password"
        label="New password"
        autocomplete="new-password"
        hint="At least 8 characters. Avoid common passwords."
        :error-messages="errors.fields.password"
      />
      <v-btn type="submit" color="primary" size="large" block :loading="busy">
        Set new password
      </v-btn>
    </v-form>
  </AuthPanel>

  <div v-else-if="state === 'invalid'" class="ll-content">
    <StatePanel
      as="h1"
      tone="warning"
      :icon="mdiLinkOff"
      title="This link has expired or was already used"
      text="Reset links work once and only for a few days. Ask for a new one."
    >
      <template #actions>
        <v-btn color="primary" @click="startOver">Get a new link</v-btn>
      </template>
    </StatePanel>
  </div>

  <div v-else class="ll-content">
    <StatePanel
      as="h1"
      :icon="mdiLockCheckOutline"
      title="Your password was changed"
      text="Sign in with your new password."
    >
      <template #actions>
        <v-btn color="primary" :to="{ name: 'signin' }">Sign in</v-btn>
      </template>
    </StatePanel>
  </div>
</template>
