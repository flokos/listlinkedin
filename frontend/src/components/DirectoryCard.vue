<script setup lang="ts">
// One public list or group in Explore: its name, description, owner, size and tags. A tag
// narrows the search to it (or, when already chosen, widens it again).
import { mdiFolderMultipleOutline, mdiFormatListBulletedSquare } from '@mdi/js'
import { computed } from 'vue'

import type { GroupDetail, ListDetail } from '../api'
import { useNow } from '../composables/useNow'
import { timeAgo } from '../utils/time'

const props = defineProps<{
  item: ListDetail | GroupDetail
  /** The tags the search is narrowed to. */
  chosenTags: string[]
}>()
const emit = defineEmits<{ tag: [tag: string] }>()

const now = useNow()
const isGroup = computed(() => 'list_count' in props.item)
const to = computed(() =>
  isGroup.value
    ? { name: 'group', params: { code: props.item.code, slug: props.item.slug } }
    : { name: 'list', params: { code: props.item.code, slug: props.item.slug } },
)
const size = computed(() => {
  const n = 'list_count' in props.item ? props.item.list_count : props.item.link_count
  const noun = isGroup.value ? 'list' : 'link'
  return `${n} ${noun}${n === 1 ? '' : 's'}`
})
const facts = computed(() =>
  [
    props.item.owner?.display_name && `By ${props.item.owner.display_name}`,
    size.value,
    `Updated ${timeAgo(props.item.updated_at, now.value)}`,
  ]
    .filter(Boolean)
    .join(' · '),
)
</script>

<template>
  <v-card class="ll-dir-card pa-4 h-100">
    <div class="d-flex ga-4">
      <v-avatar v-if="item.image_url" :image="item.image_url" size="48" rounded="lg" />
      <v-avatar v-else color="primary-container" size="48" rounded="lg">
        <v-icon :icon="isGroup ? mdiFolderMultipleOutline : mdiFormatListBulletedSquare" />
      </v-avatar>
      <div class="ll-dir-card__body">
        <h2 class="text-title-medium">
          <router-link :to="to" class="ll-dir-card__title">{{ item.title }}</router-link>
        </h2>
        <p v-if="item.description" class="ll-dir-card__description text-body-medium mt-1">
          {{ item.description }}
        </p>
        <p class="text-body-small text-medium-emphasis mt-2">{{ facts }}</p>
        <ul v-if="item.tags.length" class="ll-dir-card__tags mt-3" aria-label="Tags">
          <li v-for="tag in item.tags" :key="tag">
            <v-chip
              tag="button"
              type="button"
              size="small"
              :variant="chosenTags.includes(tag) ? 'flat' : 'outlined'"
              :color="chosenTags.includes(tag) ? 'primary' : undefined"
              :aria-pressed="chosenTags.includes(tag)"
              :aria-label="`Filter by ${tag}`"
              @click="emit('tag', tag)"
              >{{ tag }}</v-chip
            >
          </li>
        </ul>
      </div>
    </div>
  </v-card>
</template>

<style scoped>
.ll-dir-card__body {
  min-width: 0;
}
.ll-dir-card__title {
  color: rgb(var(--v-theme-on-surface));
  text-decoration: none;
  overflow-wrap: anywhere;
}
.ll-dir-card__title:hover,
.ll-dir-card__title:focus-visible {
  color: rgb(var(--v-theme-primary));
  text-decoration: underline;
}
.ll-dir-card__description {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}
.ll-dir-card__tags {
  list-style: none;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
