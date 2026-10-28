<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AuthPanel from '../components/AuthPanel.vue'
import PasswordField from '../components/PasswordField.vue'
import { useNotify } from '../composables/useNotify'
import { useSession } from '../composables/useSession'
import { formErrors, noErrors } from '../utils/forms'
import { safeRedirectPath } from '../utils/url'

const route = useRoute()
const router = useRouter()
const session = useSession()
const notify = useNotify()

const FIELDS = ['display_name', 'email', 'password'] as const
const displayName = ref('')
const email = ref('')
const password = ref('')
const errors = ref(noErrors(FIELDS))
const busy = ref(false)

async function onSubmit() {
  errors.value = noErrors(FIELDS)
  if (!email.value.trim()) errors.value.fields.email = ['Enter your email address.']
  if (!password.value) errors.value.fields.password = ['Choose a password.']
  if (FIELDS.some((f) => errors.value.fields[f].length)) return
  busy.value = true
  try {
    await session.signUp(email.value.trim(), password.value)
  } catch (error) {
    errors.value = formErrors(error, FIELDS)
    busy.value = false
    return
  }
  // The account exists now. A failed name update is not worth blocking on: it can be
  // set again on the account page.
  const name = displayName.value.trim()
  if (name) await session.updateDisplayName(name).catch(() => {})
  busy.value = false
  notify.success('Account created. Check your inbox to verify your email.')
  await router.replace(safeRedirectPath(route.query.next, '/account'))
}
</script>

<template>
  <AuthPanel
    title="Create your account"
    text="An account keeps your lists in one place, on every device."
  >
    <v-alert v-if="errors.form" type="error" class="mb-4" :text="errors.form" />
    <v-form class="d-flex flex-column ga-4" novalidate @submit.prevent="onSubmit">
      <v-text-field
        v-model="displayName"
        label="Your name (optional)"
        autocomplete="name"
        maxlength="80"
        hint="Shown to people you share lists with. You can change it later."
        persistent-hint
        :error-messages="errors.fields.display_name"
        hide-details="auto"
      />
      <v-text-field
        v-model="email"
        label="Email"
        type="email"
        autocomplete="email"
        :error-messages="errors.fields.email"
        hide-details="auto"
      />
      <PasswordField
        v-model="password"
        label="Password"
        autocomplete="new-password"
        hint="At least 8 characters. Avoid common passwords."
        :error-messages="errors.fields.password"
      />
      <v-btn type="submit" color="primary" size="large" block :loading="busy">
        Create account
      </v-btn>
    </v-form>
    <template #footer>
      Already have an account?
      <router-link :to="{ name: 'signin', query: route.query }">Sign in</router-link>
    </template>
  </AuthPanel>
</template>
