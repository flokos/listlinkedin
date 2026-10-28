<script setup lang="ts">
import { mdiTimerSandComplete, mdiTimerSandEmpty } from '@mdi/js'
import { computed } from 'vue'

import { useNow } from '../composables/useNow'
import { expiryInfo, formatDateTime } from '../utils/time'

const props = defineProps<{ expiresAt: string }>()
const now = useNow()
const info = computed(() => expiryInfo(props.expiresAt, now.value))
const exact = computed(
  () =>
    `${info.value.tone === 'expired' ? 'Expired' : 'Expires'} ${formatDateTime(props.expiresAt)}`,
)
const color = computed(
  () => ({ normal: 'primary', warning: 'warning', expired: 'error' })[info.value.tone],
)
</script>

<template>
  <!-- Exact date in a native tooltip and for screen readers; the visible label stays short. -->
  <v-chip
    :color="color"
    :prepend-icon="info.tone === 'expired' ? mdiTimerSandComplete : mdiTimerSandEmpty"
    :title="exact"
  >
    {{ info.label }}<span class="ll-sr-only"> ({{ formatDateTime(expiresAt) }})</span>
  </v-chip>
</template>
