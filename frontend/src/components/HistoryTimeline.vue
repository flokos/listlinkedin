<script setup lang="ts">
// A list's versions, newest first. Each is a link to `?v=N`, so a version can be bookmarked
// and Back returns to the previous one.
import type { Revision } from '../api'
import { describeRevision, summaryParts } from '../utils/history'
import { formatDate, timeAgo } from '../utils/time'

defineProps<{ revisions: Revision[]; selected: number | undefined; head: number; more: boolean }>()
const emit = defineEmits<{ more: [] }>()
</script>

<template>
  <nav aria-label="Versions">
    <ol class="ll-timeline">
      <li v-for="revision in revisions" :key="revision.number">
        <router-link
          :to="{ query: { v: revision.number } }"
          replace
          class="ll-timeline__item"
          :class="{ 'll-timeline__item--selected': revision.number === selected }"
          :aria-current="revision.number === selected ? 'true' : undefined"
        >
          <span class="ll-timeline__title text-title-small">
            Version {{ revision.number }}
            <span v-if="revision.number === head" class="ll-timeline__current text-label-small"
              >Current</span
            >
          </span>
          <span class="ll-timeline__line text-body-small">
            {{ describeRevision(revision) }} ·
            <time :datetime="revision.created_at" :title="formatDate(revision.created_at)">{{
              timeAgo(revision.created_at)
            }}</time>
          </span>
          <span
            v-if="summaryParts(revision.summary).length"
            class="ll-timeline__line text-body-small"
          >
            {{ summaryParts(revision.summary).join(' · ') }}
          </span>
        </router-link>
      </li>
    </ol>
    <v-btn v-if="more" variant="text" block class="mt-2" @click="emit('more')"
      >Show older versions</v-btn
    >
  </nav>
</template>

<style scoped>
.ll-timeline {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 4px;
}
.ll-timeline__item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 16px;
  border-radius: 12px;
  border-left: 4px solid transparent;
  color: rgb(var(--v-theme-on-surface));
  text-decoration: none;
}
.ll-timeline__item:hover {
  background: rgba(var(--v-theme-on-surface), 0.05);
}
.ll-timeline__item:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 2px;
}
.ll-timeline__item--selected {
  background: rgb(var(--v-theme-surface));
  border-left-color: rgb(var(--v-theme-primary));
  box-shadow: 0 1px 4px rgba(var(--v-theme-on-surface), 0.08);
}
.ll-timeline__title {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ll-timeline__current {
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid rgb(var(--v-theme-primary));
  color: rgb(var(--v-theme-primary));
}
.ll-timeline__line {
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
</style>
