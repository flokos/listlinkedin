<script setup lang="ts">
// Choosing the list to save to: one radio per list the account may add links to, with a
// search box when there are many and a group filter when the account has groups.
import { computed } from 'vue'

import { type GroupSummary, LINKS_PER_LIST } from '../lib/lists'
import type { ListSummary } from '../lib/storage'
import { VISIBILITY } from '../lib/visibility'

const props = defineProps<{
  /** The lists to offer, already filtered and ordered. */
  lists: ListSummary[]
  /** How many there are before the search narrows them: the search box shows from seven. */
  total: number
  groups: GroupSummary[]
  loading: boolean
}>()
const selected = defineModel<string>({ required: true })
const query = defineModel<string>('query', { required: true })
const group = defineModel<string>('group', { required: true })

const full = (list: ListSummary) => list.linkCount >= LINKS_PER_LIST
const about = (list: ListSummary) =>
  full(list)
    ? `Full (${LINKS_PER_LIST} links)`
    : `${list.linkCount} ${list.linkCount === 1 ? 'link' : 'links'} · ${VISIBILITY[list.visibility]}`
const searchable = computed(() => props.total > 6 || query.value !== '')
</script>

<template>
  <fieldset class="picker">
    <legend class="ll-label">Save to</legend>
    <div v-if="groups.length" class="ll-field">
      <label for="picker-group" class="ll-visually-hidden">Show lists from</label>
      <select id="picker-group" v-model="group" class="ll-input">
        <option value="">All my lists</option>
        <option v-for="item in groups" :key="item.code" :value="item.code">
          Group: {{ item.title }}
        </option>
      </select>
    </div>
    <div v-if="searchable" class="ll-field">
      <label for="picker-search" class="ll-visually-hidden">Search lists</label>
      <input
        id="picker-search"
        v-model="query"
        class="ll-input"
        type="search"
        placeholder="Search lists"
        autocomplete="off"
      />
    </div>
    <p v-if="loading && !lists.length" class="ll-muted" aria-busy="true">Loading your lists…</p>
    <p v-else-if="!lists.length" class="ll-muted">
      {{
        query
          ? 'No list matches.'
          : group
            ? 'This group has no list you can add links to.'
            : 'You have no list you can add links to yet.'
      }}
    </p>
    <ul v-else class="picker__lists">
      <li v-for="list in lists" :key="list.code">
        <label class="picker__list" :class="{ 'picker__list--full': full(list) }">
          <input
            v-model="selected"
            type="radio"
            name="list"
            :value="list.code"
            :disabled="full(list)"
          />
          <span class="picker__text">
            <span class="picker__title">{{ list.title }}</span>
            <span class="picker__about ll-muted">{{ about(list) }}</span>
          </span>
        </label>
      </li>
    </ul>
  </fieldset>
</template>

<style scoped>
.picker {
  display: grid;
  gap: 8px;
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}
.picker legend {
  padding: 0;
  margin-bottom: 4px;
}
.picker__lists {
  max-height: 200px;
  margin: 0;
  padding: 4px;
  overflow-y: auto;
  border: 1px solid var(--ll-outline-variant);
  border-radius: var(--ll-radius);
  background: var(--ll-surface);
  list-style: none;
}
.picker__list {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
}
.picker__list:has(input:checked) {
  background: var(--ll-primary-container);
  color: var(--ll-on-primary-container);
}
.picker__list:has(input:checked) .picker__about {
  color: inherit;
}
.picker__list--full {
  cursor: default;
  opacity: 0.6;
}
.picker__list input {
  margin: 3px 0 0;
  accent-color: var(--ll-primary);
}
.picker__text {
  display: grid;
  min-width: 0;
}
.picker__title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}
.picker__about {
  font-size: 12px;
}
</style>
