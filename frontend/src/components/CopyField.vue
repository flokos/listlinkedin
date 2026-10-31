<script setup lang="ts">
// A read-only value with a copy button, e.g. a link to share.
import { mdiContentCopy } from '@mdi/js'

import { useClipboard } from '../composables/useClipboard'

const props = defineProps<{ label: string; value: string; what?: string; hint?: string }>()
const { copy } = useClipboard()
const select = (event: FocusEvent) => (event.target as HTMLInputElement).select()
</script>

<template>
  <v-text-field
    :model-value="value"
    :label="label"
    :hint="hint"
    :persistent-hint="Boolean(hint)"
    readonly
    class="ll-mono-field"
    @focus="select"
  >
    <template #append-inner>
      <v-btn
        :icon="mdiContentCopy"
        variant="text"
        size="small"
        :aria-label="`Copy ${(props.what ?? label).toLowerCase()}`"
        @click="copy(value, props.what ?? label)"
      />
    </template>
  </v-text-field>
</template>

<style scoped>
.ll-mono-field :deep(input) {
  font-family: var(--ll-font-mono);
  font-size: 0.875rem;
}
</style>
