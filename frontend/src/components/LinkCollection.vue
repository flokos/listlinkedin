<script setup lang="ts">
// The links in the chosen layout, tiles (grid) or rows (list). When the order can be changed
// here (custom order, no search), they can be dragged; the ⋮ menu offers the same moves
// without dragging. Dragging only reports the move; the page applies it.
import { ref, watch } from 'vue'
import { VueDraggable, type DraggableEvent } from 'vue-draggable-plus'

import type { SharedLink } from '../api'
import type { LinkView } from '../composables/useViewPreference'
import LinkCard from './LinkCard.vue'
import LinkTile from './LinkTile.vue'

const props = defineProps<{
  links: SharedLink[]
  view: LinkView
  canEdit: boolean
  /** The shown order is the stored order, so moves (dragging, Move items) make sense. */
  reorderable: boolean
  canMoveToList: boolean
}>()
const emit = defineEmits<{
  details: [SharedLink]
  edit: [SharedLink]
  delete: [SharedLink]
  move: [SharedLink, number]
  'move-to-position': [SharedLink]
  'move-to-list': [SharedLink]
}>()

// The draggable works on its own copy, so a drop shows at once; the page's answer replaces it.
const items = ref<SharedLink[]>([...props.links])
watch(
  () => props.links,
  (links) => (items.value = [...links]),
)

let dragged = false
function onEnd(event: DraggableEvent) {
  const { oldIndex, newIndex } = event
  if (oldIndex === undefined || newIndex === undefined || oldIndex === newIndex) return
  dragged = true
  setTimeout(() => (dragged = false)) // after the click that ends a mouse drag
  emit('move', props.links[oldIndex]!, newIndex)
}
/** A drop must not also open the tile's link. */
function blockClickAfterDrag(event: MouseEvent) {
  if (dragged) {
    event.preventDefault()
    event.stopPropagation()
  }
}

const placeOf = (index: number) =>
  props.reorderable && props.canEdit ? { index, count: props.links.length } : null
</script>

<template>
  <VueDraggable
    v-model="items"
    :target="view === 'grid' ? '.ll-link-grid' : '.ll-link-rows'"
    :disabled="!(reorderable && canEdit)"
    :animation="150"
    :force-fallback="true"
    :delay="250"
    :delay-on-touch-only="true"
    :fallback-tolerance="4"
    filter=".ll-link-menu"
    :prevent-on-filter="false"
    ghost-class="ll-drag-ghost"
    chosen-class="ll-drag-chosen"
    @end="onEnd"
    @click.capture="blockClickAfterDrag"
  >
    <TransitionGroup
      v-if="view === 'grid'"
      name="ll-list"
      tag="div"
      class="ll-link-grid"
      :class="{ 'll-link-grid--draggable': reorderable && canEdit }"
    >
      <LinkTile
        v-for="(link, index) in items"
        :key="link.id"
        :link="link"
        :can-edit="canEdit"
        :place="placeOf(index)"
        :can-move-to-list="canMoveToList"
        @details="emit('details', link)"
        @edit="emit('edit', link)"
        @delete="emit('delete', link)"
        @move="emit('move', link, $event)"
        @move-to-position="emit('move-to-position', link)"
        @move-to-list="emit('move-to-list', link)"
      />
    </TransitionGroup>
    <TransitionGroup v-else name="ll-list" tag="div" class="ll-link-rows d-flex flex-column ga-3">
      <LinkCard
        v-for="(link, index) in items"
        :key="link.id"
        :link="link"
        :can-edit="canEdit"
        :place="placeOf(index)"
        :can-move-to-list="canMoveToList"
        @details="emit('details', link)"
        @edit="emit('edit', link)"
        @delete="emit('delete', link)"
        @move="emit('move', link, $event)"
        @move-to-position="emit('move-to-position', link)"
        @move-to-list="emit('move-to-list', link)"
      />
    </TransitionGroup>
  </VueDraggable>
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
.ll-link-grid--draggable :deep(.ll-tile) {
  cursor: grab;
}
:deep(.ll-drag-ghost) {
  opacity: 0.4;
}
:deep(.ll-drag-chosen) {
  box-shadow: 0 4px 16px rgba(var(--v-theme-primary), 0.25);
}
</style>
