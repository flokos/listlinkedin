<script setup lang="ts">
// Tiles in a responsive grid: as many 168 px columns as fit, two on phones.
import type { SharedLink } from '../api'
import LinkTile from './LinkTile.vue'

defineProps<{ links: SharedLink[]; canEdit: boolean }>()
const emit = defineEmits<{ details: [SharedLink]; edit: [SharedLink]; delete: [SharedLink] }>()
</script>

<template>
  <TransitionGroup name="ll-list" tag="div" class="ll-link-grid">
    <LinkTile
      v-for="link in links"
      :key="link.id"
      :link="link"
      :can-edit="canEdit"
      @details="emit('details', link)"
      @edit="emit('edit', link)"
      @delete="emit('delete', link)"
    />
  </TransitionGroup>
</template>

<style scoped>
.ll-link-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
@media (min-width: 600px) {
  .ll-link-grid {
    grid-template-columns: repeat(auto-fill, minmax(168px, 1fr));
    gap: 16px;
  }
}
</style>
