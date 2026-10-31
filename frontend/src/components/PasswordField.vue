<script setup lang="ts">
// A password input with a show/hide toggle. The toggle is a real button with a pressed
// state, so screen-reader and keyboard users can check what they typed too.
import { mdiEyeOffOutline, mdiEyeOutline } from '@mdi/js'
import { ref } from 'vue'

const password = defineModel<string>({ required: true })
defineProps<{
  label: string
  autocomplete: 'current-password' | 'new-password'
  errorMessages?: string[]
  hint?: string
}>()
const visible = ref(false)
</script>

<template>
  <v-text-field
    v-model="password"
    :label="label"
    :type="visible ? 'text' : 'password'"
    :autocomplete="autocomplete"
    :error-messages="errorMessages"
    :hint="hint"
    :persistent-hint="Boolean(hint)"
    hide-details="auto"
    spellcheck="false"
  >
    <template #append-inner>
      <v-btn
        :icon="visible ? mdiEyeOffOutline : mdiEyeOutline"
        variant="text"
        size="small"
        density="comfortable"
        :aria-label="visible ? 'Hide password' : 'Show password'"
        :aria-pressed="visible"
        @click="visible = !visible"
      />
    </template>
  </v-text-field>
</template>
