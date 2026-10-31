<script setup lang="ts">
// The "Links" heading with search, sort and the grid/list switch. Search and the non-custom
// sorts are views: they never change the stored order (docs/v2/11-UI-UX-MIGRATION.md#list-page).
import { mdiCheck, mdiMagnify, mdiSort } from '@mdi/js'
import { onBeforeUnmount, onMounted, ref } from 'vue'

import type { LinkView } from '../composables/useViewPreference'
import ViewToggle from './ViewToggle.vue'

export type LinkSort = 'custom' | 'newest' | 'az'

const props = defineProps<{ count: number }>()
const search = defineModel<string>('search', { required: true })
const sort = defineModel<LinkSort>('sort', { required: true })
const view = defineModel<LinkView>('view', { required: true })

const SORTS: { value: LinkSort; title: string }[] = [
  { value: 'custom', title: 'Custom order' },
  { value: 'newest', title: 'Newest' },
  { value: 'az', title: 'A–Z' },
]
const searchField = ref<{ focus: () => void }>()

// "/" focuses search, as in many web apps.
function onKeydown(event: KeyboardEvent) {
  const target = event.target as HTMLElement
  if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey) return
  if (target.closest('input, textarea, [contenteditable="true"]')) return
  if (props.count < 2) return
  event.preventDefault()
  searchField.value?.focus()
}
onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="d-flex flex-wrap align-center ga-3 mb-4">
    <h2 id="links-heading" class="text-title-large flex-grow-1">Links</h2>
    <template v-if="count > 1">
      <v-text-field
        ref="searchField"
        v-model="search"
        :prepend-inner-icon="mdiMagnify"
        placeholder="Search links"
        aria-label="Search links"
        density="compact"
        hide-details
        clearable
        class="ll-search"
      >
        <template #append-inner>
          <kbd v-if="!search" class="ll-kbd d-none d-md-inline-block" title="Press / to search"
            >/</kbd
          >
        </template>
      </v-text-field>
      <v-menu location="bottom end">
        <template #activator="{ props: menu }">
          <v-btn
            v-bind="menu"
            variant="outlined"
            :prepend-icon="mdiSort"
            :aria-label="`Sort: ${SORTS.find((s) => s.value === sort)!.title}`"
          >
            {{ SORTS.find((s) => s.value === sort)!.title }}
          </v-btn>
        </template>
        <v-list role="menu" density="compact" nav min-width="180">
          <v-list-item
            v-for="option in SORTS"
            :key="option.value"
            role="menuitemradio"
            :aria-checked="sort === option.value"
            :title="option.title"
            @click="sort = option.value"
          >
            <template #append>
              <v-icon v-if="sort === option.value" :icon="mdiCheck" size="18" />
            </template>
          </v-list-item>
        </v-list>
      </v-menu>
    </template>
    <ViewToggle v-if="count > 0" v-model="view" />
  </div>
</template>

<style scoped>
.ll-kbd {
  padding: 0 6px;
  border-radius: 4px;
  border: 1px solid rgba(var(--v-border-color), 0.3);
  font-family: var(--ll-font-mono);
  font-size: 0.75rem;
  line-height: 1.4;
  opacity: var(--v-medium-emphasis-opacity);
}
.ll-search {
  max-width: 280px;
  min-width: 180px;
}
</style>
