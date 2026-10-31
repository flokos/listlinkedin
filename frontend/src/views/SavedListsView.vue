<script setup lang="ts">
// My lists: the lists in the signed-in account, owned or shared with you. (Lists saved in this
// browser with an edit link were retired in task 9.6.)
import { mdiFormatListBulletedSquare, mdiPlus } from '@mdi/js'
import { ref, watch } from 'vue'

import { type ListDetail, myLists } from '../api'
import ExpiryChip from '../components/ExpiryChip.vue'
import StatePanel from '../components/StatePanel.vue'
import { useSession } from '../composables/useSession'

const session = useSession()

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
</script>

<template>
  <div class="ll-content py-6 py-md-10">
    <div class="d-flex flex-wrap align-end justify-space-between ga-4 mb-2">
      <div>
        <h1 class="text-headline-large">My lists</h1>
        <p class="text-body-large text-medium-emphasis ll-reading mt-1">
          Lists in your account, and lists people have shared with you.
        </p>
      </div>
      <v-btn
        v-if="session.isSignedIn.value"
        color="primary"
        :prepend-icon="mdiPlus"
        :to="{ name: 'home', hash: '#create' }"
        >New list</v-btn
      >
    </div>

    <section v-if="session.isSignedIn.value" class="mt-8" aria-labelledby="account-heading">
      <h2 id="account-heading" class="text-title-large mb-3">Your lists</h2>
      <v-progress-linear v-if="accountState === 'loading'" indeterminate color="primary" />
      <v-alert
        v-else-if="accountState === 'error'"
        type="error"
        text="Couldn't load your lists. Try again in a moment."
      />
      <StatePanel
        v-else-if="!accountLists.length"
        :icon="mdiFormatListBulletedSquare"
        title="No lists yet"
        text="Create a list, or ask someone to share theirs with you."
      >
        <template #actions>
          <v-btn color="primary" :to="{ name: 'home', hash: '#create' }">Create a list</v-btn>
        </template>
      </StatePanel>
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
      title="Sign in to see your lists"
      text="Your lists are kept in your account, on every device."
    >
      <template #append>
        <v-btn variant="flat" color="primary" :to="{ name: 'signin', query: { next: '/lists' } }"
          >Sign in</v-btn
        >
      </template>
    </v-alert>
  </div>
</template>

<style scoped>
.ll-lists {
  list-style: none;
  display: grid;
  gap: 12px;
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
</style>
