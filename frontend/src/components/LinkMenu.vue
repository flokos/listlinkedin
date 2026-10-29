<script setup lang="ts">
// The ⋮ menu of a link, the same in grid and list view (docs/v2/11-UI-UX-MIGRATION.md#list-page).
import {
  mdiContentCopy,
  mdiDeleteOutline,
  mdiDotsVertical,
  mdiInformationOutline,
  mdiOpenInNew,
  mdiPencilOutline,
} from '@mdi/js'

import { useClipboard } from '../composables/useClipboard'

defineProps<{ heading: string; href: string; shortUrl: string | null; canEdit: boolean }>()
const emit = defineEmits<{ details: []; edit: []; delete: [] }>()
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
      <template v-if="canEdit">
        <v-divider class="my-1" />
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
