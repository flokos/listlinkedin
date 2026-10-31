<script setup lang="ts">
// Everything about one link, for every viewer: the full name and description (tiles clamp
// them), the destination and the short link. Editors can fetch the page's details again.
import { mdiRefresh } from '@mdi/js'
import { computed, ref, watch } from 'vue'

import { errorMessage, type SharedLink } from '../api'
import { displayHost } from '../utils/url'
import { formatDate } from '../utils/time'
import CopyField from './CopyField.vue'
import LinkIcon from './LinkIcon.vue'

const open = defineModel<boolean>({ required: true })
const props = defineProps<{
  link: SharedLink | null
  /** Editors: fetch the page's details again. */
  refresh?: () => Promise<unknown>
}>()

const refreshing = ref(false)
const refreshNote = ref<{ text: string; error: boolean } | null>(null)
watch(open, () => (refreshNote.value = null))

async function refreshDetails() {
  if (!props.refresh) return
  refreshing.value = true
  refreshNote.value = null
  try {
    await props.refresh()
    refreshNote.value = { text: 'Fetching the details again…', error: false }
  } catch (error) {
    refreshNote.value = { text: errorMessage(error), error: true }
  } finally {
    refreshing.value = false
  }
}

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
          <LinkIcon
            :url="link.destination_url"
            :icon-url="display.icon_url"
            :size="56"
            :pending="link.metadata_status === 'pending'"
          />
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
        <p
          v-if="link.metadata_status === 'pending'"
          class="text-body-small text-medium-emphasis mb-2"
        >
          Fetching details from the site…
        </p>
        <p
          v-else-if="link.metadata_status === 'unavailable'"
          class="text-body-small text-medium-emphasis mb-2"
        >
          Couldn't fetch details for this site. You can add a title and description yourself.
        </p>
        <p
          v-if="refreshNote"
          class="text-body-small mb-2"
          :class="refreshNote.error ? 'text-error' : 'text-medium-emphasis'"
          role="status"
        >
          {{ refreshNote.text }}
        </p>
        <p class="text-body-small text-medium-emphasis mb-0">
          Added {{ formatDate(link.created_at) }}
        </p>
      </v-card-text>
      <v-card-actions>
        <v-btn
          v-if="refresh && link.metadata_status && link.metadata_status !== 'disabled'"
          variant="text"
          :prepend-icon="mdiRefresh"
          :loading="refreshing"
          @click="refreshDetails"
        >
          Refresh details
        </v-btn>
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
