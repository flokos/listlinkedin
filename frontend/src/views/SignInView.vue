<script setup lang="ts">
import { computed, ref } from 'vue'
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

const FIELDS = ['email', 'password'] as const
const email = ref('')
const password = ref('')
const errors = ref(noErrors(FIELDS))
const busy = ref(false)
const next = computed(() => safeRedirectPath(route.query.next))

async function onSubmit() {
  errors.value = noErrors(FIELDS)
  if (!email.value.trim()) errors.value.fields.email = ['Enter your email address.']
  if (!password.value) errors.value.fields.password = ['Enter your password.']
  if (FIELDS.some((f) => errors.value.fields[f].length)) return
  busy.value = true
  try {
    await session.signIn(email.value.trim(), password.value)
    notify.success('Signed in')
    await router.replace(next.value)
  } catch (error) {
    errors.value = formErrors(error, FIELDS)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <AuthPanel title="Sign in" text="Welcome back. Sign in to manage your lists.">
    <v-alert v-if="errors.form" type="error" class="mb-4" :text="errors.form" />
    <v-form class="d-flex flex-column ga-4" novalidate @submit.prevent="onSubmit">
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
        autocomplete="current-password"
        :error-messages="errors.fields.password"
      />
      <router-link :to="{ name: 'reset-password' }" class="text-body-medium align-self-end">
        Forgot your password?
      </router-link>
      <v-btn type="submit" color="primary" size="large" block :loading="busy">Sign in</v-btn>
    </v-form>
    <template #footer>
      New here?
      <router-link :to="{ name: 'signup', query: route.query }">Create an account</router-link>
    </template>
  </AuthPanel>
</template>
