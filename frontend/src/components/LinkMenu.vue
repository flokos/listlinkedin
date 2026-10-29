<script setup lang="ts">
// The ⋮ menu of a link, the same in grid and list view (docs/v2/11-UI-UX-MIGRATION.md#list-page).
import {
  mdiArrowCollapseDown,
  mdiArrowCollapseUp,
  mdiArrowDown,
  mdiArrowUp,
  mdiContentCopy,
  mdiFolderMoveOutline,
  mdiFormatListNumbered,
  mdiDeleteOutline,
  mdiDotsVertical,
  mdiInformationOutline,
  mdiOpenInNew,
  mdiPencilOutline,
} from '@mdi/js'

import { useClipboard } from '../composables/useClipboard'

defineProps<{
  heading: string
  href: string
  shortUrl: string | null
  canEdit: boolean
  /** Where the link is, when it can be moved here (custom order, no search); else null. */
  place?: { index: number; count: number } | null
  /** Offers "Move to another list…" (accounts that can edit other lists). */
  canMoveToList?: boolean
}>()
const emit = defineEmits<{
  details: []
  edit: []
  delete: []
  /** Move within the list to this 0-based index. */
  move: [index: number]
  'move-to-position': []
  'move-to-list': []
}>()
const { copy } = useClipboard()
</script>

<template>
  <v-menu location="bottom end">
    <template #activator="{ props: menu }">
      <v-btn
        v-bind="menu"
        :icon="mdiDotsVertical"
        variant="text"
        size="small"
        :aria-label="`More actions for ${heading}`"
        class="ll-link-menu"
      />
    </template>
    <v-list role="menu" density="compact" nav min-width="200">
      <v-list-item
        role="menuitem"
        :prepend-icon="mdiOpenInNew"
        title="Open"
        :href="href"
        target="_blank"
        rel="noopener noreferrer"
      />
      <v-list-item
        v-if="shortUrl"
        role="menuitem"
        :prepend-icon="mdiContentCopy"
        title="Copy short link"
        @click="copy(shortUrl, 'Short link')"
      />
      <v-list-item
        role="menuitem"
        :prepend-icon="mdiInformationOutline"
        title="Details"
        @click="emit('details')"
      />
      <template v-if="canEdit && place">
        <v-divider class="my-1" />
        <!-- Moving without dragging (WCAG 2.2 SC 2.5.7): every move dragging can make.
             Vuetify doesn't expose `disabled` to assistive technology, hence aria-disabled. -->
        <v-list-item
          role="menuitem"
          :prepend-icon="mdiArrowUp"
          title="Move up"
          :disabled="place.index === 0"
          :aria-disabled="place.index === 0"
          @click="emit('move', place.index - 1)"
        />
        <v-list-item
          role="menuitem"
          :prepend-icon="mdiArrowDown"
          title="Move down"
          :disabled="place.index === place.count - 1"
          :aria-disabled="place.index === place.count - 1"
          @click="emit('move', place.index + 1)"
        />
        <v-list-item
          role="menuitem"
          :prepend-icon="mdiArrowCollapseUp"
          title="Move to top"
          :disabled="place.index === 0"
          :aria-disabled="place.index === 0"
          @click="emit('move', 0)"
        />
        <v-list-item
          role="menuitem"
          :prepend-icon="mdiArrowCollapseDown"
          title="Move to bottom"
          :disabled="place.index === place.count - 1"
          :aria-disabled="place.index === place.count - 1"
          @click="emit('move', place.count - 1)"
        />
        <v-list-item
          role="menuitem"
          :prepend-icon="mdiFormatListNumbered"
          title="Move to position…"
          :disabled="place.count < 2"
          :aria-disabled="place.count < 2"
          @click="emit('move-to-position')"
        />
      </template>
      <template v-if="canEdit">
        <v-divider class="my-1" />
        <v-list-item
          v-if="canMoveToList"
          role="menuitem"
          :prepend-icon="mdiFolderMoveOutline"
          title="Move to another list…"
          @click="emit('move-to-list')"
        />
        <v-list-item
          role="menuitem"
          :prepend-icon="mdiPencilOutline"
          title="Edit"
          @click="emit('edit')"
        />
        <v-list-item
          role="menuitem"
          :prepend-icon="mdiDeleteOutline"
          title="Delete"
          base-color="error"
          @click="emit('delete')"
        />
      </template>
    </v-list>
  </v-menu>
</template>
