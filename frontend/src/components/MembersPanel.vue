<script setup lang="ts">
// The People section of the Share dialog: who the list is shared with. The owner adds
// existing accounts by email, changes roles and removes people; editors only see the list.
import { mdiAccountPlusOutline, mdiClose } from '@mdi/js'
import { onMounted, ref } from 'vue'

import {
  addMember,
  ApiError,
  changeMember,
  errorMessage,
  listMembers,
  type Member,
  type MemberRole,
  removeMember,
} from '../api'
import { useNotify } from '../composables/useNotify'

const props = defineProps<{
  code: string
  /** The owner's name as the list shows it, or null when they haven't set one. */
  ownerName: string | null
  youAreOwner: boolean
  /** The owner may add people, change roles and remove people. */
  canManage: boolean
  /** Adding people needs a verified email address. */
  emailVerified: boolean
}>()

const notify = useNotify()
const roles: { title: string; value: MemberRole }[] = [
  { title: 'Can edit', value: 'editor' },
  { title: 'Can view', value: 'viewer' },
]

const members = ref<Member[]>([])
const loading = ref(true)
const loadError = ref<string>()

const email = ref('')
const role = ref<MemberRole>('viewer')
const emailError = ref<string[]>([])
const adding = ref(false)
const emailField = ref<{ focus: () => void }>()

const nameOf = (m: Member) => m.display_name || m.email_hint

async function load() {
  loading.value = true
  try {
    members.value = (await listMembers(props.code)).results
    loadError.value = undefined
  } catch (error) {
    loadError.value = errorMessage(error)
  } finally {
    loading.value = false
  }
}
onMounted(load)

async function add() {
  emailError.value = []
  const address = email.value.trim()
  if (!address) {
    emailError.value = ['Enter the email address of their account.']
    emailField.value?.focus()
    return
  }
  adding.value = true
  try {
    const member = await addMember(props.code, address, role.value)
    members.value = [...members.value, member]
    email.value = ''
    notify.success(
      `${nameOf(member)} can now ${member.role === 'editor' ? 'edit' : 'view'} this list`,
    )
    emailField.value?.focus()
  } catch (error) {
    if (error instanceof ApiError && error.fieldErrors.email) {
      emailError.value = error.fieldErrors.email
      emailField.value?.focus()
    } else {
      notify.error(errorMessage(error))
    }
  } finally {
    adding.value = false
  }
}

async function setRole(member: Member, next: MemberRole) {
  if (next === member.role) return
  try {
    const updated = await changeMember(props.code, member.user_id, next)
    members.value = members.value.map((m) => (m.user_id === updated.user_id ? updated : m))
    notify.success(
      `${nameOf(updated)} can now ${next === 'editor' ? 'edit' : 'only view'} this list`,
    )
  } catch (error) {
    notify.error(errorMessage(error))
  }
}

async function remove(member: Member) {
  try {
    await removeMember(props.code, member.user_id)
    members.value = members.value.filter((m) => m.user_id !== member.user_id)
    notify.success(`Removed ${nameOf(member)}`)
  } catch (error) {
    notify.error(errorMessage(error))
  }
}
</script>

<template>
  <section aria-labelledby="people-heading" class="mt-6">
    <h3 id="people-heading" class="text-title-medium mb-2">People</h3>

    <template v-if="canManage">
      <v-alert
        v-if="!emailVerified"
        type="info"
        variant="tonal"
        density="compact"
        class="mb-3"
        text="Verify your email address on your account page to add people."
      />
      <form class="ll-add-person mb-2" novalidate @submit.prevent="add">
        <v-text-field
          ref="emailField"
          v-model="email"
          label="Email address"
          type="email"
          autocomplete="off"
          :disabled="!emailVerified || adding"
          :error-messages="emailError"
          hint="They need an account with this address."
          @update:model-value="emailError = []"
        />
        <v-select
          v-model="role"
          :items="roles"
          label="Permission"
          :disabled="!emailVerified || adding"
          class="ll-role"
        />
        <v-btn
          type="submit"
          color="primary"
          variant="tonal"
          size="large"
          :prepend-icon="mdiAccountPlusOutline"
          :loading="adding"
          :disabled="!emailVerified"
        >
          Add
        </v-btn>
      </form>
    </template>

    <v-skeleton-loader v-if="loading" type="list-item-two-line@2" />
    <v-alert v-else-if="loadError" type="error" variant="tonal" density="compact" :text="loadError">
      <template #append>
        <v-btn variant="text" @click="load">Try again</v-btn>
      </template>
    </v-alert>
    <v-list v-else aria-label="People with access" density="compact" class="pa-0">
      <v-list-item
        :title="youAreOwner ? 'You' : ownerName || 'The owner'"
        subtitle="Owner"
        class="px-0"
      />
      <v-list-item
        v-for="member in members"
        :key="member.user_id"
        :title="member.is_you ? 'You' : nameOf(member)"
        :subtitle="member.display_name ? member.email_hint : undefined"
        class="px-0"
      >
        <template #append>
          <template v-if="canManage">
            <v-select
              :model-value="member.role"
              :items="roles"
              :aria-label="`Permission for ${nameOf(member)}`"
              density="compact"
              variant="plain"
              hide-details
              class="ll-member-role"
              @update:model-value="(value) => setRole(member, value as MemberRole)"
            />
            <v-btn
              :icon="mdiClose"
              variant="text"
              size="small"
              :aria-label="`Remove ${nameOf(member)}`"
              @click="remove(member)"
            />
          </template>
          <span v-else class="text-body-medium text-medium-emphasis">
            {{ member.role === 'editor' ? 'Can edit' : 'Can view' }}
          </span>
        </template>
      </v-list-item>
    </v-list>
    <p
      v-if="!loading && !loadError && !members.length"
      class="text-body-small text-medium-emphasis"
    >
      Nobody else has access yet.
    </p>
  </section>
</template>

<style scoped>
.ll-add-person {
  display: grid;
  grid-template-columns: 1fr;
  gap: 4px 12px;
  align-items: start;
}
@media (min-width: 600px) {
  .ll-add-person {
    grid-template-columns: 1fr 150px auto;
  }
  .ll-add-person .v-btn {
    margin-top: 4px;
  }
}
.ll-member-role {
  width: 120px;
}
</style>
