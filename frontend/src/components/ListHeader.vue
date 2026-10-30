<script setup lang="ts">
// The list's name (renamable), its state chips and tags, Share and the list's ⋮ menu.
import {
  mdiAccountArrowLeftOutline,
  mdiCheck,
  mdiClose,
  mdiContentCopy,
  mdiDeleteOutline,
  mdiDotsVertical,
  mdiHistory,
  mdiKeyChange,
  mdiLogout,
  mdiPencilOutline,
  mdiShareVariant,
  mdiShieldKeyOutline,
  mdiTagMultipleOutline,
  mdiTrayRemove,
} from '@mdi/js'
import { nextTick, ref } from 'vue'

import { errorMessage, LIMITS, type ListDetail } from '../api'
import { formatDate } from '../utils/time'
import ExpiryChip from './ExpiryChip.vue'

const props = defineProps<{
  list: ListDetail
  linkCount: number
  /** May edit (owner, editor, or this browser's edit link). */
  canEdit: boolean
  /** This browser holds the list's edit link. */
  hasToken: boolean
  can: (permission: string) => boolean
  /** Signed out, on a list whose owner allows copies: "Make a copy" asks to sign in first. */
  signInToCopy?: boolean
  /** Saves a new name; throws to show the error. Returns false if the editor should close
   * without an error (edit access was lost; the page explains it). */
  rename: (title: string) => Promise<boolean>
}>()
const emit = defineEmits<{
  share: []
  claim: []
  'show-edit-link': []
  rotate: []
  forget: []
  leave: []
  delete: []
  copy: []
  tags: []
}>()

const renaming = ref(false)
const newTitle = ref('')
const renameError = ref<string[]>([])
const renameBusy = ref(false)
const renameField = ref<{ focus: () => void }>()

async function startRename() {
  newTitle.value = props.list.title
  renameError.value = []
  renaming.value = true
  await nextTick()
  renameField.value?.focus()
}

async function saveRename() {
  const title = newTitle.value.trim()
  if (!title) {
    renameError.value = ['A list needs a name.']
    return
  }
  if (title === props.list.title) {
    renaming.value = false
    return
  }
  renameBusy.value = true
  try {
    await props.rename(title)
    renaming.value = false
  } catch (error) {
    renameError.value = [errorMessage(error)]
  } finally {
    renameBusy.value = false
  }
}

defineExpose({ startRename, stopRename: () => (renaming.value = false) })
</script>

<template>
  <header class="ll-list-header mb-6">
    <div class="d-flex flex-wrap align-start ga-4">
      <div class="flex-grow-1 ll-list-header__main">
        <p class="text-label-large text-primary mb-1">
          {{
            list.my_role === 'owner' || (list.legacy && canEdit)
              ? 'Your list'
              : canEdit
                ? 'You can edit this list'
                : 'Shared list'
          }}
        </p>
        <v-form v-if="renaming" class="d-flex align-start ga-2" @submit.prevent="saveRename">
          <v-text-field
            ref="renameField"
            v-model="newTitle"
            label="List name"
            :maxlength="LIMITS.titleLength"
            :error-messages="renameError"
            hide-details="auto"
            class="flex-grow-1"
            @keydown.esc="renaming = false"
          />
          <v-btn
            type="submit"
            :icon="mdiCheck"
            color="primary"
            :loading="renameBusy"
            aria-label="Save name"
          />
          <v-btn
            :icon="mdiClose"
            variant="text"
            aria-label="Cancel renaming"
            @click="renaming = false"
          />
        </v-form>
        <h1 v-else class="text-headline-large ll-list-title">
          {{ list.title }}
          <v-btn
            v-if="canEdit"
            icon
            variant="text"
            density="comfortable"
            class="ll-list-title__edit"
            aria-label="Rename list"
            @click="startRename"
          >
            <v-icon :icon="mdiPencilOutline" size="20" />
          </v-btn>
        </h1>
        <div class="d-flex flex-wrap align-center ga-2 mt-3">
          <v-chip v-if="list.visibility === 'private'" color="secondary" variant="outlined"
            >Only people you add</v-chip
          >
          <ExpiryChip v-if="list.expires_at" :expires-at="list.expires_at" />
          <v-chip color="secondary">{{ linkCount }} link{{ linkCount === 1 ? '' : 's' }}</v-chip>
          <span class="text-body-small text-medium-emphasis"
            >Created {{ formatDate(list.created_at) }}</span
          >
        </div>
        <ul v-if="list.tags.length" class="ll-list-tags mt-3" aria-label="Tags">
          <li v-for="tag in list.tags" :key="tag">
            <v-chip
              size="small"
              variant="outlined"
              :to="{ name: 'explore', query: { tags: tag } }"
              :aria-label="`${tag}: explore lists with this tag`"
              >{{ tag }}</v-chip
            >
          </li>
        </ul>
        <!-- Only when the reader can open the source: a copy never reveals a hidden list. -->
        <p v-if="list.origin?.parent" class="text-body-medium text-medium-emphasis mt-3">
          <v-icon :icon="mdiContentCopy" size="16" class="mr-1" aria-hidden="true" />
          Copied from
          <router-link :to="{ name: 'list', params: { code: list.origin.parent.code } }">{{
            list.origin.parent.title
          }}</router-link>
        </p>
      </div>

      <div class="d-flex align-center ga-1">
        <v-btn
          color="primary"
          :variant="canEdit ? 'tonal' : 'flat'"
          :prepend-icon="mdiShareVariant"
          @click="emit('share')"
        >
          Share
        </v-btn>
        <v-menu
          v-if="canEdit || can('delete') || can('leave') || can('fork') || signInToCopy"
          location="bottom end"
        >
          <template #activator="{ props: menu }">
            <v-btn v-bind="menu" :icon="mdiDotsVertical" variant="text" aria-label="List options" />
          </template>
          <v-list role="menu" density="comfortable" nav min-width="240">
            <v-list-item
              v-if="canEdit"
              role="menuitem"
              :prepend-icon="mdiPencilOutline"
              title="Rename"
              @click="startRename"
            />
            <v-list-item
              v-if="can('tags')"
              role="menuitem"
              :prepend-icon="mdiTagMultipleOutline"
              title="Tags…"
              @click="emit('tags')"
            />
            <v-list-item
              v-if="can('view_history')"
              role="menuitem"
              :prepend-icon="mdiHistory"
              title="History"
              :to="{ name: 'list-history', params: { code: list.code } }"
            />
            <v-list-item
              v-if="can('fork') || signInToCopy"
              role="menuitem"
              :prepend-icon="mdiContentCopy"
              title="Make a copy…"
              @click="emit('copy')"
            />
            <v-list-item
              v-if="list.legacy && hasToken"
              role="menuitem"
              :prepend-icon="mdiAccountArrowLeftOutline"
              title="Add to my account"
              @click="emit('claim')"
            />
            <v-list-item
              v-if="list.legacy && hasToken"
              role="menuitem"
              :prepend-icon="mdiShieldKeyOutline"
              title="Show edit link"
              @click="emit('show-edit-link')"
            />
            <v-list-item
              v-if="can('rotate_token')"
              role="menuitem"
              :prepend-icon="mdiKeyChange"
              title="Replace edit link"
              @click="emit('rotate')"
            />
            <v-divider class="my-1" />
            <v-list-item
              v-if="hasToken"
              role="menuitem"
              :prepend-icon="mdiTrayRemove"
              title="Forget on this device"
              @click="emit('forget')"
            />
            <v-list-item
              v-if="can('leave')"
              role="menuitem"
              :prepend-icon="mdiLogout"
              title="Leave list"
              @click="emit('leave')"
            />
            <v-list-item
              v-if="can('delete')"
              role="menuitem"
              :prepend-icon="mdiDeleteOutline"
              title="Delete list"
              base-color="error"
              @click="emit('delete')"
            />
          </v-list>
        </v-menu>
      </div>
    </div>
  </header>
</template>

<style scoped>
.ll-list-header__main {
  min-width: 0;
  flex-basis: 320px;
}
.ll-list-tags {
  list-style: none;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.ll-list-title {
  overflow-wrap: anywhere;
}
.ll-list-title__edit {
  vertical-align: middle;
  opacity: 0.6;
}
.ll-list-title__edit:hover,
.ll-list-title__edit:focus-visible {
  opacity: 1;
}
</style>
