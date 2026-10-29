<script setup lang="ts">
// The links in the chosen layout: tiles (grid) or rows (list).
import type { SharedLink } from '../api'
import type { LinkView } from '../composables/useViewPreference'
import LinkCard from './LinkCard.vue'
import LinkGrid from './LinkGrid.vue'

defineProps<{ links: SharedLink[]; view: LinkView; canEdit: boolean }>()
const emit = defineEmits<{ details: [SharedLink]; edit: [SharedLink]; delete: [SharedLink] }>()
</script>

<template>
  <LinkGrid
    v-if="view === 'grid'"
    :links="links"
    :can-edit="canEdit"
    @details="emit('details', $event)"
    @edit="emit('edit', $event)"
    @delete="emit('delete', $event)"
  />
  <TransitionGroup v-else name="ll-list" tag="div" class="d-flex flex-column ga-3">
    <LinkCard
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
