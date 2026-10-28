<script setup lang="ts">
import { mdiTimerSandComplete, mdiTimerSandEmpty } from '@mdi/js'
import { computed } from 'vue'

import { useNow } from '../composables/useNow'
import { expiryInfo, formatDateTime } from '../utils/time'

const props = defineProps<{ expiresAt: string }>()
const now = useNow()
const info = computed(() => expiryInfo(props.expiresAt, now.value))
const color = computed(
  () => ({ normal: 'primary', warning: 'warning', expired: 'error' })[info.value.tone],
)
</script>

<template>
  <v-tooltip
    :text="`${info.tone === 'expired' ? 'Expired' : 'Expires'} ${formatDateTime(expiresAt)}`"
  >
    <template #activator="{ props: tip }">
      <v-chip
        v-bind="tip"
        :color="color"
        :prepend-icon="info.tone === 'expired' ? mdiTimerSandComplete : mdiTimerSandEmpty"
        tabindex="0"
      >
        {{ info.label }}
      </v-chip>
    </template>
  </v-tooltip>
</template>
