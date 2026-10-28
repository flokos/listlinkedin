<script setup lang="ts">
import {
  mdiContentCopy,
  mdiDeleteOutline,
  mdiDotsVertical,
  mdiOpenInNew,
  mdiPencilOutline,
} from '@mdi/js'
import { computed } from 'vue'

import type { SharedLink } from '../api'
import { useClipboard } from '../composables/useClipboard'
import { displayHost, displayUrl } from '../utils/url'
import { timeAgo } from '../utils/time'
import DomainAvatar from './DomainAvatar.vue'

const props = defineProps<{ link: SharedLink; owner: boolean }>()
const emit = defineEmits<{ edit: []; delete: [] }>()
const { copy } = useClipboard()

/** Visitors go through the short link, which always resolves to the current destination. */
const href = computed(() => props.link.short_url ?? props.link.destination_url)
const heading = computed(() => props.link.title || displayHost(props.link.destination_url))
</script>

<template>
  <article class="ll-link-card d-flex align-center ga-3 ga-sm-4 pa-3 pa-sm-4">
    <DomainAvatar :url="link.destination_url" />
    <div class="flex-grow-1 ll-link-card__body">
      <a
        :href="href"
        target="_blank"
        rel="noopener noreferrer"
        class="ll-link-card__title text-title-medium"
      >
        {{ heading }}
        <span class="ll-sr-only">(opens in a new tab)</span>
      </a>
      <p
        class="text-body-small text-medium-emphasis ma-0 text-truncate"
        :title="link.destination_url"
      >
        {{ displayUrl(link.destination_url) }}
      </p>
      <p v-if="owner" class="text-label-small text-medium-emphasis ma-0 mt-1">
        Added {{ timeAgo(link.created_at) }}
      </p>
    </div>
    <div class="d-flex align-center flex-shrink-0">
      <v-btn
        v-if="link.short_url"
        :icon="mdiContentCopy"
        variant="text"
        size="small"
        :aria-label="`Copy short link for ${heading}`"
        @click="copy(link.short_url, 'Short link')"
      />
      <v-btn
        :icon="mdiOpenInNew"
        variant="text"
        size="small"
        :href="href"
        target="_blank"
        rel="noopener noreferrer"
        :aria-label="`Open ${heading} in a new tab`"
        class="d-none d-sm-inline-flex"
      />
      <v-menu v-if="owner" location="bottom end">
        <template #activator="{ props: menu }">
          <v-btn
            v-bind="menu"
            :icon="mdiDotsVertical"
            variant="text"
            size="small"
            :aria-label="`More actions for ${heading}`"
          />
        </template>
        <v-list density="compact" nav>
          <v-list-item :prepend-icon="mdiPencilOutline" title="Edit" @click="emit('edit')" />
          <v-list-item
            :prepend-icon="mdiDeleteOutline"
            title="Delete"
            base-color="error"
            @click="emit('delete')"
          />
        </v-list>
      </v-menu>
    </div>
  </article>
</template>

<style scoped>
.ll-link-card {
  border-radius: 16px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  transition:
    border-color var(--ll-duration-base) var(--ll-ease-standard),
    box-shadow var(--ll-duration-base) var(--ll-ease-standard);
}
.ll-link-card:hover {
  border-color: rgba(var(--v-theme-primary), 0.45);
  box-shadow: 0 2px 12px rgba(var(--v-theme-primary), 0.08);
}
.ll-link-card__body {
  min-width: 0;
}
.ll-link-card__title {
  color: rgb(var(--v-theme-on-surface));
  text-decoration: none;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}
.ll-link-card__title:hover {
  color: rgb(var(--v-theme-primary));
  text-decoration: underline;
}
</style>
