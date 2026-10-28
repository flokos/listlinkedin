<script setup lang="ts">
import { computed } from 'vue'

import { LIMITS } from '../api'

const props = defineProps<{ count: number }>()
const ratio = computed(() => props.count / LIMITS.linksPerList)
const color = computed(() =>
  ratio.value >= 1 ? 'error' : ratio.value >= 0.9 ? 'warning' : 'primary',
)
</script>

<template>
  <div class="ll-meter" :title="`${count} of ${LIMITS.linksPerList} links used`">
    <div class="d-flex justify-space-between text-label-medium mb-1">
      <span class="text-medium-emphasis">Links</span>
      <span>{{ count }} / {{ LIMITS.linksPerList }}</span>
    </div>
    <v-progress-linear
      :model-value="ratio * 100"
      :color="color"
      bg-color="outline-variant"
      bg-opacity="1"
      rounded
      height="6"
      :aria-label="`${count} of ${LIMITS.linksPerList} links used`"
    />
  </div>
</template>

<style scoped>
.ll-meter {
  min-width: 140px;
}
</style>
