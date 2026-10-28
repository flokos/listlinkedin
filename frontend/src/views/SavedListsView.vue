<script setup lang="ts">
import {
  mdiArrowRight,
  mdiContentCopy,
  mdiDotsVertical,
  mdiFormatListBulletedSquare,
  mdiKeyOutline,
  mdiPlus,
  mdiTrayRemove,
} from '@mdi/js'
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { ApiError, getList } from '../api'
import BackupCard from '../components/BackupCard.vue'
import ClaimTokenDialog from '../components/ClaimTokenDialog.vue'
import ExpiryChip from '../components/ExpiryChip.vue'
import StatePanel from '../components/StatePanel.vue'
import { useClipboard } from '../composables/useClipboard'
import { useNotify } from '../composables/useNotify'
import { type OwnedList, useOwnedLists } from '../composables/useOwnedLists'

type Health = 'checking' | 'active' | 'expired' | 'deleted' | 'unknown'

const owned = useOwnedLists()
const router = useRouter()
const notify = useNotify()
const { copy } = useClipboard()
const health = reactive<Record<string, Health>>({})
const claimOpen = ref(false)

// Check each saved list against the server, so deleted or expired ones are clearly marked.
onMounted(() => {
  for (const item of owned.lists.value) {
    health[item.code] = 'checking'
    getList(item.code)
      .then((list) => {
        health[item.code] = 'active'
        owned.update(item.code, { title: list.title, expiresAt: list.expires_at })
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
        <h1 class="text-headline-large">Saved lists</h1>
        <p class="text-body-large text-medium-emphasis ll-reading mt-1">
          Lists you can edit from this browser. They're saved on this device only, not in an
          account. To use them elsewhere, open their edit links there or restore a backup.
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
        <v-btn color="primary" :prepend-icon="mdiPlus" :to="{ name: 'home', hash: '#create' }"
          >New list</v-btn
        >
      </div>
    </div>

    <StatePanel
      v-if="!owned.lists.value.length"
      :icon="mdiFormatListBulletedSquare"
      title="No lists on this device yet"
      text="Create a list, open one you made elsewhere with its edit link, or restore a backup."
      class="mt-8"
    >
      <template #actions>
        <v-btn color="primary" :to="{ name: 'home', hash: '#create' }">Create a list</v-btn>
        <v-btn variant="tonal" color="primary" @click="claimOpen = true">Use an edit link</v-btn>
      </template>
    </StatePanel>

    <TransitionGroup v-else name="ll-list" tag="ul" class="ll-lists mt-8 pa-0">
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
