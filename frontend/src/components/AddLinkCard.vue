<script setup lang="ts">
import { mdiLinkVariantPlus } from '@mdi/js'

import { LIMITS, type LinkInput } from '../api'
import LinkForm from './LinkForm.vue'
import LinkLimitMeter from './LinkLimitMeter.vue'

const props = defineProps<{ count: number; submit: (input: LinkInput) => Promise<unknown> }>()
</script>

<template>
  <v-card class="pa-4 pa-sm-5 mb-8 ll-add-card" color="surface-container">
    <div class="d-flex flex-wrap align-center justify-space-between ga-4 mb-4">
      <h2 class="text-title-large d-flex align-center ga-2">
        <v-icon :icon="mdiLinkVariantPlus" color="primary" /> Add a link
      </h2>
      <LinkLimitMeter :count="props.count" />
    </div>
    <v-alert
      v-if="props.count >= LIMITS.linksPerList"
      type="info"
      density="compact"
      class="mb-3"
      text="This list has reached its limit of 100 links. Delete one to add another."
    />
    <LinkForm mode="add" :disabled="props.count >= LIMITS.linksPerList" :submit="submit" />
  </v-card>
</template>

<style scoped>
.ll-add-card {
  border-color: rgba(var(--v-theme-primary), 0.25) !important;
}
</style>
