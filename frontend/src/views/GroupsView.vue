<script setup lang="ts">
// My groups: the groups you own or were added to. `list_count` counts only the lists each
// group shows you.
import { mdiFolderMultipleOutline, mdiPlus } from '@mdi/js'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { createGroup, errorMessage, type GroupDetail, type GroupInput, myGroups } from '../api'
import GroupFormDialog from '../components/GroupFormDialog.vue'
import StatePanel from '../components/StatePanel.vue'
import { useNotify } from '../composables/useNotify'

const router = useRouter()
const notify = useNotify()
const groups = ref<GroupDetail[]>([])
const state = ref<'loading' | 'ready' | 'error'>('loading')
const loadError = ref('')
const createOpen = ref(false)

async function load() {
  state.value = 'loading'
  try {
    groups.value = (await myGroups()).results
    state.value = 'ready'
  } catch (error) {
    loadError.value = errorMessage(error)
    state.value = 'error'
  }
}
onMounted(load)

async function create(input: GroupInput) {
  const group = await createGroup(input)
  notify.success(`Created “${group.title}”`)
  await router.push({ name: 'group', params: { code: group.code, slug: group.slug } })
}

const roleLabel = { owner: 'Owner', editor: 'Editor', viewer: 'Viewer' } as const
const visibilityLabel = {
  private: 'Only people you add',
  unlisted: 'Anyone with the link',
  public: 'Public',
} as const
</script>

<template>
  <div class="ll-content py-6 py-md-10">
    <div class="d-flex flex-wrap align-end justify-space-between ga-4 mb-8">
      <div>
        <h1 class="text-headline-large">Groups</h1>
        <p class="text-body-large text-medium-emphasis ll-reading mt-1">
          Workspaces of lists, with a sidebar to move between them.
        </p>
      </div>
      <v-btn color="primary" :prepend-icon="mdiPlus" @click="createOpen = true">New group</v-btn>
    </div>

    <v-progress-linear
      v-if="state === 'loading'"
      indeterminate
      color="primary"
      aria-label="Loading your groups"
    />
    <v-alert v-else-if="state === 'error'" type="error" :text="loadError">
      <template #append>
        <v-btn variant="text" @click="load">Try again</v-btn>
      </template>
    </v-alert>
    <StatePanel
      v-else-if="!groups.length"
      :icon="mdiFolderMultipleOutline"
      title="No groups yet"
      text="Put related lists together, for example a team's tools, and share them as one link."
    >
      <template #actions>
        <v-btn color="primary" :prepend-icon="mdiPlus" @click="createOpen = true">New group</v-btn>
      </template>
    </StatePanel>
    <ul v-else class="ll-groups pa-0" aria-label="Your groups">
      <li v-for="group in groups" :key="group.id">
        <v-card class="pa-4 d-flex align-center ga-4">
          <v-avatar v-if="group.image_url" :image="group.image_url" size="48" rounded="lg" />
          <v-avatar v-else color="primary-container" size="48" rounded="lg">
            <v-icon :icon="mdiFolderMultipleOutline" />
          </v-avatar>
          <div class="ll-groups__body">
            <router-link
              :to="{ name: 'group', params: { code: group.code, slug: group.slug } }"
              class="ll-groups__title text-title-medium"
            >
              {{ group.title }}
            </router-link>
            <div class="d-flex flex-wrap align-center ga-2 mt-2">
              <v-chip v-if="group.my_role" color="primary">{{ roleLabel[group.my_role] }}</v-chip>
              <v-chip variant="outlined">{{ visibilityLabel[group.visibility] }}</v-chip>
              <span class="text-body-small text-medium-emphasis"
                >{{ group.list_count }} list{{ group.list_count === 1 ? '' : 's' }}</span
              >
            </div>
          </div>
        </v-card>
      </li>
    </ul>

    <GroupFormDialog v-model="createOpen" :submit="create" />
  </div>
</template>

<style scoped>
.ll-groups {
  list-style: none;
  display: grid;
  gap: 12px;
}
.ll-groups__body {
  min-width: 0;
}
.ll-groups__title {
  color: rgb(var(--v-theme-on-surface));
  text-decoration: none;
  overflow-wrap: anywhere;
}
.ll-groups__title:hover {
  color: rgb(var(--v-theme-primary));
  text-decoration: underline;
}
</style>
