<script setup lang="ts">
// Announces short status messages to screen readers without moving focus, e.g. where a moved
// link ended up. Repeating a message is announced again (the text is cleared first).
import { nextTick, ref, watch } from 'vue'

const props = defineProps<{ message: { text: string } | null }>()
const text = ref('')
watch(
  () => props.message,
  async (message) => {
    text.value = ''
    await nextTick()
    text.value = message?.text ?? ''
  },
)
</script>

<template>
  <div class="ll-sr-only" role="status" aria-live="polite" aria-atomic="true">{{ text }}</div>
</template>
