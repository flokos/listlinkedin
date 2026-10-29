<script setup lang="ts">
import {
  mdiAccountArrowLeftOutline,
  mdiArrowRight,
  mdiContentCopy,
  mdiDotsVertical,
  mdiFormatListBulletedSquare,
  mdiKeyOutline,
  mdiPlus,
  mdiTrayRemove,
} from '@mdi/js'
import { onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { ApiError, claimList, errorMessage, getList, type ListDetail, myLists } from '../api'
import BackupCard from '../components/BackupCard.vue'
import ClaimTokenDialog from '../components/ClaimTokenDialog.vue'
import ExpiryChip from '../components/ExpiryChip.vue'
import StatePanel from '../components/StatePanel.vue'
import { useClipboard } from '../composables/useClipboard'
import { useNotify } from '../composables/useNotify'
import { type OwnedList, useOwnedLists } from '../composables/useOwnedLists'
import { useSession } from '../composables/useSession'

type Health = 'checking' | 'active' | 'expired' | 'deleted' | 'unknown'

const owned = useOwnedLists()
const router = useRouter()
const notify = useNotify()
const { copy } = useClipboard()
const health = reactive<Record<string, Health>>({})
const claimOpen = ref(false)
const session = useSession()

// Lists in the signed-in account (owned or shared with you).
const accountLists = ref<ListDetail[]>([])
const accountState = ref<'idle' | 'loading' | 'ready' | 'error'>('idle')
async function loadAccountLists() {
  if (!session.isSignedIn.value) {
    accountLists.value = []
    accountState.value = 'idle'
    return
  }
  accountState.value = 'loading'
  try {
    accountLists.value = (await myLists()).results
    accountState.value = 'ready'
  } catch {
    accountState.value = 'error'
  }
}
watch(() => session.user.value?.id, loadAccountLists, { immediate: true })

const roleLabel = { owner: 'Owner', editor: 'Editor', viewer: 'Viewer' } as const
const visibilityLabel = {
  private: 'Only people you add',
  unlisted: 'Anyone with the link',
  public: 'Public',
} as const

// Moving lists from this device into the account.
const claiming = ref(new Set<string>())
async function addToAccount(item: OwnedList, quiet = false): Promise<boolean> {
  claiming.value = new Set(claiming.value).add(item.code)
  try {
    await claimList(item.code, item.token)
    owned.forget(item.code)
    if (!quiet) notify.success(`Added “${item.title || 'Untitled list'}” to your account`)
    return true
  } catch (error) {
    notify.error(`${item.title || 'Untitled list'}: ${errorMessage(error)}`)
    return false
  } finally {
    const next = new Set(claiming.value)
    next.delete(item.code)
    claiming.value = next
  }
}
async function addAllToAccount() {
  const usable = owned.lists.value.filter((item) => health[item.code] === 'active')
  let added = 0
  for (const item of usable) if (await addToAccount(item, true)) added += 1
  if (added) notify.success(`Added ${added} list${added === 1 ? '' : 's'} to your account`)
  await loadAccountLists()
}
async function addOne(item: OwnedList) {
  if (await addToAccount(item)) await loadAccountLists()
}

// Check each saved list against the server, so deleted or expired ones are clearly marked.
onMounted(() => {
  for (const item of owned.lists.value) {
    health[item.code] = 'checking'
    getList(item.code)
      .then((list) => {
        health[item.code] = 'active'
        owned.update(item.code, { title: list.title, expiresAt: list.expires_at ?? '' })
      })
      .catch((error) => {
        health[item.code] =
          error instanceof ApiError && error.status === 404
            ? 'deleted'
            : error instanceof ApiError && error.status === 410
              ? 'expired'
              : 'unknown'
      })
  }
})

const publicUrl = (item: OwnedList) => `${window.location.origin}/l/${item.code}`

function forget(item: OwnedList) {
  owned.forget(item.code)
  notify.info(`Removed “${item.title || 'Untitled list'}” from this device`)
}
</script>

<template>
  <div class="ll-content py-6 py-md-10">
    <div class="d-flex flex-wrap align-end justify-space-between ga-4 mb-2">
      <div>
        <h1 class="text-headline-large">My lists</h1>
        <p class="text-body-large text-medium-emphasis ll-reading mt-1">
          Lists in your account, and lists this browser can edit with an edit link.
        </p>
      </div>
      <div class="d-flex ga-2">
        <v-btn
          variant="tonal"
          color="primary"
          :prepend-icon="mdiKeyOutline"
          @click="claimOpen = true"
        >
          Add with edit link
        </v-btn>
        <v-btn
          v-if="session.isSignedIn.value"
          color="primary"
          :prepend-icon="mdiPlus"
          :to="{ name: 'home', hash: '#create' }"
          >New list</v-btn
        >
      </div>
    </div>

    <section v-if="session.isSignedIn.value" class="mt-8" aria-labelledby="account-heading">
      <h2 id="account-heading" class="text-title-large mb-3">Your lists</h2>
      <v-progress-linear v-if="accountState === 'loading'" indeterminate color="primary" />
      <v-alert
        v-else-if="accountState === 'error'"
        type="error"
        text="Couldn't load your lists. Try again in a moment."
      />
      <p v-else-if="!accountLists.length" class="text-body-medium text-medium-emphasis">
        No lists in your account yet. Create one, or add the lists below.
      </p>
      <ul v-else class="ll-lists pa-0">
        <li v-for="item in accountLists" :key="item.id">
          <v-card class="pa-4">
            <router-link
              :to="{ name: 'list', params: { code: item.code, slug: item.slug } }"
              class="ll-lists__title text-title-medium"
            >
              {{ item.title || 'Untitled list' }}
            </router-link>
            <div class="d-flex flex-wrap align-center ga-2 mt-2">
              <v-chip v-if="item.my_role" color="primary">{{ roleLabel[item.my_role] }}</v-chip>
              <v-chip variant="outlined">{{ visibilityLabel[item.visibility] }}</v-chip>
              <ExpiryChip v-if="item.expires_at" :expires-at="item.expires_at" />
              <span class="text-body-small text-medium-emphasis"
                >{{ item.link_count }} link{{ item.link_count === 1 ? '' : 's' }}</span
              >
            </div>
          </v-card>
        </li>
      </ul>
    </section>
    <v-alert
      v-else-if="session.ready.value"
      type="info"
      class="mt-8"
      title="Keep your lists in an account"
      text="Sign in to see your lists on every device, and add the lists saved in this browser to your account."
    >
      <template #append>
        <v-btn variant="flat" color="primary" :to="{ name: 'signin', query: { next: '/lists' } }"
          >Sign in</v-btn
        >
      </template>
    </v-alert>

    <div class="d-flex flex-wrap align-center justify-space-between ga-3 mt-10">
      <h2 class="text-title-large">On this device</h2>
      <v-btn
        v-if="session.isSignedIn.value && owned.lists.value.length"
        variant="tonal"
        color="primary"
        :prepend-icon="mdiAccountArrowLeftOutline"
        :loading="claiming.size > 0"
        @click="addAllToAccount"
      >
        Add all to my account
      </v-btn>
    </div>

    <StatePanel
      v-if="!owned.lists.value.length"
      :icon="mdiFormatListBulletedSquare"
      title="No lists on this device yet"
      text="Create a list, open one you made elsewhere with its edit link, or restore a backup."
      class="mt-4"
    >
      <template #actions>
        <v-btn color="primary" :to="{ name: 'home', hash: '#create' }">Create a list</v-btn>
        <v-btn variant="tonal" color="primary" @click="claimOpen = true">Use an edit link</v-btn>
      </template>
    </StatePanel>

    <TransitionGroup v-else name="ll-list" tag="ul" class="ll-lists mt-4 pa-0">
      <li v-for="item in owned.lists.value" :key="item.code">
        <v-card
          class="pa-4 d-flex align-center ga-4"
          :class="{ 'll-lists__gone': ['expired', 'deleted'].includes(health[item.code] ?? '') }"
        >
          <div class="flex-grow-1 ll-lists__body">
            <router-link
              :to="{ name: 'list', params: { code: item.code } }"
              class="ll-lists__title text-title-medium"
            >
              {{ item.title || 'Untitled list' }}
            </router-link>
            <div class="d-flex flex-wrap align-center ga-2 mt-2">
              <v-chip v-if="health[item.code] === 'deleted'" color="error">Deleted</v-chip>
              <v-chip v-else-if="health[item.code] === 'expired'" color="error">Expired</v-chip>
              <ExpiryChip v-else-if="item.expiresAt" :expires-at="item.expiresAt" />
              <v-progress-circular
                v-if="health[item.code] === 'checking'"
                indeterminate
                size="16"
                width="2"
                color="primary"
                aria-label="Checking status"
              />
            </div>
          </div>
          <v-btn
            v-if="session.isSignedIn.value && health[item.code] === 'active'"
            variant="tonal"
            color="primary"
            size="small"
            :loading="claiming.has(item.code)"
            :aria-label="`Add ${item.title || 'Untitled list'} to my account`"
            @click="addOne(item)"
          >
            Add to my account
          </v-btn>
          <v-btn
            v-if="['expired', 'deleted'].includes(health[item.code] ?? '')"
            variant="tonal"
            :prepend-icon="mdiTrayRemove"
            @click="forget(item)"
          >
            Remove
          </v-btn>
          <template v-else>
            <v-btn
              :icon="mdiArrowRight"
              variant="text"
              :aria-label="`Open ${item.title || 'list'}`"
              @click="router.push({ name: 'list', params: { code: item.code } })"
            />
            <v-menu location="bottom end">
              <template #activator="{ props }">
                <v-btn
                  v-bind="props"
                  :icon="mdiDotsVertical"
                  variant="text"
                  :aria-label="`More actions for ${item.title || 'list'}`"
                />
              </template>
              <v-list role="menu" density="compact" nav>
                <v-list-item
                  role="menuitem"
                  :prepend-icon="mdiContentCopy"
                  title="Copy share link"
                  @click="copy(publicUrl(item), 'Share link')"
                />
                <v-list-item
                  role="menuitem"
                  :prepend-icon="mdiTrayRemove"
                  title="Forget on this device"
                  @click="forget(item)"
                />
              </v-list>
            </v-menu>
          </template>
        </v-card>
      </li>
    </TransitionGroup>

    <BackupCard class="mt-10" />

    <ClaimTokenDialog
      v-model="claimOpen"
      @claimed="(code) => router.push({ name: 'list', params: { code } })"
    />
  </div>
</template>

<style scoped>
.ll-lists {
  list-style: none;
  display: grid;
  gap: 12px;
}
.ll-lists__body {
  min-width: 0;
}
.ll-lists__title {
  color: rgb(var(--v-theme-on-surface));
  text-decoration: none;
  overflow-wrap: anywhere;
}
.ll-lists__title:hover {
  color: rgb(var(--v-theme-primary));
  text-decoration: underline;
}
.ll-lists__gone .ll-lists__title {
  text-decoration: line-through;
  opacity: var(--v-medium-emphasis-opacity);
}
.ll-list-enter-active,
.ll-list-leave-active {
  transition:
    opacity var(--ll-duration-base) var(--ll-ease-standard),
    transform var(--ll-duration-base) var(--ll-ease-standard);
}
.ll-list-enter-from,
.ll-list-leave-to {
  opacity: 0;
  transform: translateX(16px);
}
</style>
