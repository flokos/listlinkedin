<script setup lang="ts">
// "Make a copy" (docs/v2/11-UI-UX-MIGRATION.md#copy-synced-copy-and-history): an independent
// list the user owns. Synced copies are postponed (ADR-015), so this offers only the copy.
import { mdiContentCopy, mdiLockOutline } from '@mdi/js'
import { nextTick, ref, watch } from 'vue'

import { ApiError, errorMessage, forkList, LIMITS, type ListDetail } from '../api'

const open = defineModel<boolean>({ required: true })
const props = defineProps<{ list: ListDetail }>()
/** The copy was made. The dialog doesn't close itself: the parent opens the copy. */
const emit = defineEmits<{ copied: [copy: ListDetail] }>()

const SUFFIX = ' (copy)'
const title = ref('')
const error = ref<string[]>([])
const busy = ref(false)
const field = ref<{ focus: () => void }>()
// One key per copy the user asks for: retrying after a lost answer returns the same copy.
let attemptKey = crypto.randomUUID()

// Immediate: after signing in, the page comes back with the dialog already open.
watch(
  open,
  async (isOpen) => {
    if (!isOpen) return
    title.value = props.list.title.slice(0, LIMITS.titleLength - SUFFIX.length) + SUFFIX
    error.value = []
    await nextTick()
    field.value?.focus()
  },
  { immediate: true },
)

async function submit() {
  const value = title.value.trim()
  if (!value) {
    error.value = ['Give the copy a name.']
    return
  }
  busy.value = true
  error.value = []
  try {
    const copy = await forkList(props.list.code, { title: value }, attemptKey)
    attemptKey = crypto.randomUUID()
    emit('copied', copy)
  } catch (e) {
    error.value =
      e instanceof ApiError ? (e.fieldErrors.title ?? [e.userMessage]) : [errorMessage(e)]
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <v-dialog v-model="open" max-width="480" :persistent="busy" aria-label="Make a copy">
    <v-card class="pa-2">
      <v-card-item>
        <v-card-title class="text-title-large">Make a copy</v-card-title>
        <v-card-subtitle class="text-wrap">{{ list.title }}</v-card-subtitle>
      </v-card-item>
      <v-form @submit.prevent="submit">
        <v-card-text class="pt-4">
          <p class="d-flex ga-3 mb-3">
            <v-icon :icon="mdiContentCopy" class="mt-1" aria-hidden="true" />
            <span>
              Your own list with the same links, which you can change as you like. Later changes to
              “{{ list.title }}” won't reach it, and yours won't reach the original.
            </span>
          </p>
          <p class="d-flex ga-3 mb-5">
            <v-icon :icon="mdiLockOutline" class="mt-1" aria-hidden="true" />
            <span>
              Only you can see the copy until you share it. Its links get new short URLs.
            </span>
          </p>
          <v-text-field
            ref="field"
            v-model="title"
            label="Name of the copy"
            :maxlength="LIMITS.titleLength"
            :error-messages="error"
            hide-details="auto"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" :disabled="busy" @click="open = false">Cancel</v-btn>
          <v-btn type="submit" color="primary" variant="flat" :loading="busy">Make a copy</v-btn>
        </v-card-actions>
      </v-form>
    </v-card>
  </v-dialog>
</template>
