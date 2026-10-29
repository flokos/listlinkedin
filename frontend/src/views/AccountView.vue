<script setup lang="ts">
import {
  mdiAccountRemoveOutline,
  mdiCheckDecagramOutline,
  mdiEmailAlertOutline,
  mdiLogout,
} from '@mdi/js'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  ApiError,
  changePassword,
  deleteAccount,
  errorMessage,
  ownedListCount,
  resendVerification,
} from '../api'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import PasswordField from '../components/PasswordField.vue'
import { useNotify } from '../composables/useNotify'
import { useSession } from '../composables/useSession'
import { useSignOut } from '../composables/useSignOut'
import { formErrors, noErrors } from '../utils/forms'

const router = useRouter()
const session = useSession()
const notify = useNotify()
const { user } = session

/** The session ended elsewhere (signed out in another tab, expired): go sign in again. */
async function handleSignedOut(error: unknown): Promise<boolean> {
  if (!(error instanceof ApiError && error.status === 401)) return false
  session.markSignedOut()
  await router.replace({ name: 'signin', query: { next: '/account' } })
  return true
}

// Profile
const PROFILE = ['display_name'] as const
const displayName = ref(user.value?.display_name ?? '')
const profileErrors = ref(noErrors(PROFILE))
const savingProfile = ref(false)
async function saveProfile() {
  profileErrors.value = noErrors(PROFILE)
  savingProfile.value = true
  try {
    await session.updateDisplayName(displayName.value.trim())
    displayName.value = user.value?.display_name ?? ''
    notify.success('Name saved')
  } catch (error) {
    if (!(await handleSignedOut(error))) profileErrors.value = formErrors(error, PROFILE)
  } finally {
    savingProfile.value = false
  }
}

// Email verification
const resending = ref(false)
async function resend() {
  if (!user.value) return
  resending.value = true
  try {
    const sent = await resendVerification(user.value.email)
    if (sent) notify.success(`We sent a verification link to ${user.value.email}.`)
    else notify.info('We sent a link recently. Check your inbox, or try again in a few minutes.')
  } catch (error) {
    if (!(await handleSignedOut(error))) notify.error(errorMessage(error))
  } finally {
    resending.value = false
  }
}

// Password
const PASSWORD = ['current_password', 'new_password'] as const
const currentPassword = ref('')
const newPassword = ref('')
const passwordErrors = ref(noErrors(PASSWORD))
const changingPassword = ref(false)
async function savePassword() {
  passwordErrors.value = noErrors(PASSWORD)
  if (!currentPassword.value)
    passwordErrors.value.fields.current_password = ['Enter your current password.']
  if (!newPassword.value) passwordErrors.value.fields.new_password = ['Choose a new password.']
  if (PASSWORD.some((f) => passwordErrors.value.fields[f].length)) return
  changingPassword.value = true
  try {
    await changePassword(currentPassword.value, newPassword.value)
    currentPassword.value = ''
    newPassword.value = ''
    notify.success('Password changed')
  } catch (error) {
    if (!(await handleSignedOut(error))) passwordErrors.value = formErrors(error, PASSWORD)
  } finally {
    changingPassword.value = false
  }
}

// Deleting the account hides the lists it owns from everyone at once and erases everything
// after 30 days; signing in before then can restore it (docs/v2/adr/ADR-016).
const deleteOpen = ref(false)
const ownedCount = ref<number>()
const preparingDelete = ref(false)
async function startDelete() {
  preparingDelete.value = true
  try {
    ownedCount.value = await ownedListCount()
    deleteOpen.value = true
  } catch (error) {
    if (!(await handleSignedOut(error))) notify.error(errorMessage(error))
  } finally {
    preparingDelete.value = false
  }
}
const deleteText = computed(() => {
  const n = ownedCount.value ?? 0
  const lists =
    n === 0
      ? "You don't own any lists."
      : `The ${n === 1 ? 'list' : `${n} lists`} you own, with all ${n === 1 ? 'its' : 'their'} links and short links, will disappear for everyone right away.`
  return `${lists} You'll be signed out everywhere and removed from lists others shared with you. Everything is erased after 30 days; until then, sign in to restore your account.`
})
async function confirmDelete() {
  if (!user.value) return
  try {
    await deleteAccount(user.value.email)
  } catch (error) {
    notify.error(errorMessage(error))
    throw error
  }
  await session.refresh()
  notify.success('Your account will be erased in 30 days. Sign in before then to restore it.')
  await router.replace({ name: 'home' })
}

const leave = useSignOut()
const signingOut = ref(false)
async function signOut() {
  signingOut.value = true
  await leave()
  signingOut.value = false
}
</script>

<template>
  <div v-if="user" class="ll-content py-6 py-md-10">
    <header class="d-flex flex-wrap align-center ga-4 mb-8">
      <div class="flex-grow-1">
        <h1 class="text-headline-large">Your account</h1>
        <p class="text-body-large text-medium-emphasis mt-1">{{ user.email }}</p>
      </div>
      <v-btn variant="tonal" :prepend-icon="mdiLogout" :loading="signingOut" @click="signOut">
        Sign out
      </v-btn>
    </header>

    <section class="ll-account-section" aria-labelledby="profile-heading">
      <h2 id="profile-heading" class="text-title-large mb-1">Profile</h2>
      <p class="text-body-medium text-medium-emphasis mb-4">
        Your name is shown to people you share lists with.
      </p>
      <v-alert v-if="profileErrors.form" type="error" class="mb-4" :text="profileErrors.form" />
      <v-form class="d-flex flex-column flex-sm-row ga-3" novalidate @submit.prevent="saveProfile">
        <v-text-field
          v-model="displayName"
          label="Your name"
          autocomplete="name"
          maxlength="80"
          :error-messages="profileErrors.fields.display_name"
          hide-details="auto"
        />
        <v-btn type="submit" color="primary" size="large" :loading="savingProfile">
          Save name
        </v-btn>
      </v-form>
    </section>

    <section class="ll-account-section" aria-labelledby="email-heading">
      <h2 id="email-heading" class="text-title-large mb-3">Email</h2>
      <div class="d-flex flex-wrap align-center ga-3">
        <span class="text-body-large">{{ user.email }}</span>
        <v-chip
          v-if="user.email_verified"
          color="success"
          :prepend-icon="mdiCheckDecagramOutline"
          text="Verified"
        />
        <v-chip v-else color="warning" :prepend-icon="mdiEmailAlertOutline" text="Not verified" />
      </div>
      <template v-if="!user.email_verified">
        <p class="text-body-medium text-medium-emphasis mt-3 mb-4">
          Open the link we emailed you to verify your address. You'll need a verified address to
          share lists publicly.
        </p>
        <v-btn variant="tonal" color="primary" :loading="resending" @click="resend">
          Send verification email
        </v-btn>
      </template>
    </section>

    <section class="ll-account-section" aria-labelledby="password-heading">
      <h2 id="password-heading" class="text-title-large mb-4">Password</h2>
      <v-alert v-if="passwordErrors.form" type="error" class="mb-4" :text="passwordErrors.form" />
      <v-form
        class="d-flex flex-column ga-4 ll-account-password"
        novalidate
        @submit.prevent="savePassword"
      >
        <PasswordField
          v-model="currentPassword"
          label="Current password"
          autocomplete="current-password"
          :error-messages="passwordErrors.fields.current_password"
        />
        <PasswordField
          v-model="newPassword"
          label="New password"
          autocomplete="new-password"
          hint="At least 8 characters. Avoid common passwords."
          :error-messages="passwordErrors.fields.new_password"
        />
        <v-btn
          type="submit"
          color="primary"
          size="large"
          class="align-self-start"
          :loading="changingPassword"
        >
          Change password
        </v-btn>
      </v-form>
    </section>

    <section class="ll-account-section" aria-labelledby="delete-heading">
      <h2 id="delete-heading" class="text-title-large mb-1">Delete account</h2>
      <p class="text-body-medium text-medium-emphasis mb-4">
        Deletes your account and the lists you own, for everyone. You can restore it by signing in
        within 30 days; after that it is erased. Lists only saved on this device with an edit link
        aren't affected.
      </p>
      <v-btn
        variant="tonal"
        color="error"
        :prepend-icon="mdiAccountRemoveOutline"
        :loading="preparingDelete"
        @click="startDelete"
      >
        Delete account…
      </v-btn>
      <ConfirmDialog
        v-model="deleteOpen"
        title="Delete your account?"
        :text="deleteText"
        action="Delete account"
        :confirm-text="user.email"
        :on-confirm="confirmDelete"
      />
    </section>
  </div>
</template>

<style scoped>
.ll-account-section {
  padding-block: 24px;
  border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.ll-account-password {
  max-width: 440px;
}
</style>
