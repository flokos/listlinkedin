<script setup lang="ts">
import { mdiLinkVariant } from '@mdi/js'
import { ref, watchEffect } from 'vue'

import { ApiError, getLinks, getList, type SharedLink, type SharedList } from '../api'

const props = defineProps<{ code: string }>()

const list = ref<SharedList>()
const links = ref<SharedLink[]>([])
const error = ref<'not-found' | 'expired' | 'failed'>()

watchEffect(async () => {
  error.value = undefined
  try {
    const [listData, linkPage] = await Promise.all([getList(props.code), getLinks(props.code)])
    list.value = listData
    links.value = linkPage.results
  } catch (e) {
    const status = e instanceof ApiError ? e.status : 0
    error.value = status === 404 ? 'not-found' : status === 410 ? 'expired' : 'failed'
  }
})

const errorTitles = {
  'not-found': 'This list does not exist',
  expired: 'This list has expired',
  failed: 'Could not load this list',
}
</script>

<template>
  <v-empty-state v-if="error" :title="errorTitles[error]" />
  <v-skeleton-loader v-else-if="!list" type="heading, list-item-two-line@3" />
  <template v-else>
    <h1 class="text-h4 mb-1">{{ list.title }}</h1>
    <p class="text-medium-emphasis mb-6">
      Expires {{ new Date(list.expires_at).toLocaleDateString() }}
    </p>
    <v-list v-if="links.length" lines="two" border rounded>
      <v-list-item
        v-for="link in links"
        :key="link.id"
        :href="link.short_url ?? link.destination_url"
        :title="link.title ?? link.destination_url"
        :subtitle="link.destination_url"
        :prepend-icon="mdiLinkVariant"
        target="_blank"
        rel="noopener noreferrer"
      />
    </v-list>
    <v-empty-state v-else title="No links yet" />
  </template>
</template>
