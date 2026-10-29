<script setup lang="ts">
// Everything about one link, for every viewer: the full name and description (tiles clamp
// them), the destination and the short link.
import { computed } from 'vue'

import type { SharedLink } from '../api'
import { displayHost } from '../utils/url'
import { formatDate } from '../utils/time'
import CopyField from './CopyField.vue'
import LinkIcon from './LinkIcon.vue'

const open = defineModel<boolean>({ required: true })
const props = defineProps<{ link: SharedLink | null }>()

const display = computed(() => {
  const link = props.link
  if (!link) return null
  return (
    link.display ?? {
      title: link.title || displayHost(link.destination_url),
      description: link.description ?? null,
      icon_url: link.icon_url ?? null,
      site_name: displayHost(link.destination_url),
    }
  )
})
</script>

<template>
  <v-dialog v-model="open" max-width="560" aria-label="Link details">
    <v-card v-if="link && display" class="pa-2">
      <v-card-item>
        <template #prepend>
          <LinkIcon :url="link.destination_url" :icon-url="display.icon_url" :size="56" />
        </template>
        <v-card-title class="ll-details__title">{{ display.title }}</v-card-title>
        <v-card-subtitle>{{ display.site_name }}</v-card-subtitle>
      </v-card-item>
      <v-card-text>
        <p v-if="display.description" class="ll-details__description text-body-medium mb-4">
          {{ display.description }}
        </p>
        <p class="text-label-large mb-1">Goes to</p>
        <p class="ll-details__url text-body-medium mb-4">
          <a
            :href="link.short_url ?? link.destination_url"
            target="_blank"
            rel="noopener noreferrer"
          >
            {{ link.destination_url }}
            <span class="ll-sr-only">(opens in a new tab)</span>
          </a>
        </p>
        <CopyField v-if="link.short_url" label="Short link" :value="link.short_url" />
        <p class="text-body-small text-medium-emphasis mb-0">
          Added {{ formatDate(link.created_at) }}
        </p>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="open = false">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.ll-details__title {
  white-space: normal;
  overflow-wrap: anywhere;
}
.ll-details__description {
  white-space: pre-line;
  overflow-wrap: anywhere;
}
.ll-details__url {
  overflow-wrap: anywhere;
}
</style>
