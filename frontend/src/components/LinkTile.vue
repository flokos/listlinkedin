<script setup lang="ts">
// A link as a tile (grid view): icon, name, site and description. The whole tile opens the
// link through its short URL, as V1's title did; the ⋮ menu sits above it, separately
// focusable (docs/v2/11-UI-UX-MIGRATION.md#list-page).
import { computed } from 'vue'
import { useDisplay } from 'vuetify'

import type { SharedLink } from '../api'
import { displayHost } from '../utils/url'
import LinkIcon from './LinkIcon.vue'
import LinkMenu from './LinkMenu.vue'

const props = defineProps<{
  link: SharedLink
  canEdit: boolean
  place?: { index: number; count: number } | null
  canMoveToList?: boolean
}>()
const emit = defineEmits<{
  details: []
  edit: []
  delete: []
  move: [index: number]
  'move-to-position': []
  'move-to-list': []
}>()
const { smAndUp } = useDisplay()

const href = computed(() => props.link.short_url ?? props.link.destination_url)
const display = computed(
  () =>
    props.link.display ?? {
      title: props.link.title || displayHost(props.link.destination_url),
      description: props.link.description ?? null,
      icon_url: props.link.icon_url ?? null,
      site_name: displayHost(props.link.destination_url),
    },
)
</script>

<template>
  <article class="ll-tile pa-3 pa-sm-4">
    <div class="ll-tile__menu">
      <LinkMenu
        :heading="display.title"
        :href="href"
        :short-url="link.short_url"
        :can-edit="canEdit"
        :place="place"
        :can-move-to-list="canMoveToList"
        @details="emit('details')"
        @edit="emit('edit')"
        @delete="emit('delete')"
        @move="emit('move', $event)"
        @move-to-position="emit('move-to-position')"
        @move-to-list="emit('move-to-list')"
      />
    </div>
    <LinkIcon
      :url="link.destination_url"
      :icon-url="display.icon_url"
      :size="smAndUp ? 128 : 72"
      class="ll-tile__icon"
    />
    <a
      :href="href"
      target="_blank"
      rel="noopener noreferrer"
      class="ll-tile__link text-title-small"
    >
      {{ display.title }}
      <span class="ll-sr-only">(opens in a new tab)</span>
    </a>
    <p class="ll-tile__site text-label-small text-medium-emphasis">{{ display.site_name }}</p>
    <p v-if="display.description" class="ll-tile__description text-body-small text-medium-emphasis">
      {{ display.description }}
    </p>
  </article>
</template>

<style scoped>
.ll-tile {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 0;
  height: 100%;
  text-align: center;
  border-radius: 16px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  transition:
    border-color var(--ll-duration-base) var(--ll-ease-standard),
    box-shadow var(--ll-duration-base) var(--ll-ease-standard);
}
.ll-tile:hover {
  border-color: rgba(var(--v-theme-primary), 0.45);
  box-shadow: 0 2px 12px rgba(var(--v-theme-primary), 0.08);
}
/* The link covers the whole tile; the outline follows the tile, not the text. */
.ll-tile:has(.ll-tile__link:focus-visible) {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 2px;
}
.ll-tile__link:focus-visible {
  outline: none;
}
.ll-tile__link::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
}
.ll-tile__menu {
  position: absolute;
  top: 4px;
  right: 4px;
  z-index: 1; /* above the link's cover */
}
.ll-tile__icon {
  margin: 4px 0 8px;
}
.ll-tile__link {
  max-width: 100%;
  color: rgb(var(--v-theme-on-surface));
  text-decoration: none;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}
.ll-tile:hover .ll-tile__link {
  color: rgb(var(--v-theme-primary));
}
.ll-tile__site {
  max-width: 100%;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ll-tile__description {
  max-width: 100%;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}
</style>
