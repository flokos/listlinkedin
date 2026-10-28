<script setup lang="ts">
// Confirmation for destructive actions. With `confirmText`, the user must type it first
// (used for deleting a whole list).
import { computed, ref, watch } from 'vue'

const open = defineModel<boolean>({ required: true })
const props = defineProps<{
  title: string
  text: string
  action: string
  confirmText?: string
  /** Runs on confirm; the dialog shows progress and closes when it resolves. */
  onConfirm: () => Promise<unknown>
}>()

const typed = ref('')
const busy = ref(false)
const canConfirm = computed(
  () => !props.confirmText || typed.value.trim() === props.confirmText.trim(),
)

watch(open, (value) => {
  if (value) typed.value = ''
})

async function confirm() {
  if (!canConfirm.value) return
  busy.value = true
  try {
    await props.onConfirm()
    open.value = false
  } catch {
    // The caller reports the error; keep the dialog open so the user can retry or cancel.
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <v-dialog v-model="open" max-width="460" :persistent="busy">
    <v-card :title="title" class="pa-2">
      <v-card-text class="text-body-medium">
        <p>{{ text }}</p>
        <v-text-field
          v-if="confirmText"
          v-model="typed"
          class="mt-4"
          :label="`Type “${confirmText}” to confirm`"
          autocomplete="off"
          hide-details="auto"
          @keyup.enter="confirm"
        />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" :disabled="busy" @click="open = false">Cancel</v-btn>
        <v-btn color="error" :disabled="!canConfirm" :loading="busy" @click="confirm">{{
          action
        }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
