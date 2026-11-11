<script setup lang="ts">
// "My lists": the account's lists and groups, to look into, open on the site and share.
import { computed, onMounted, ref, watch } from 'vue'

import { Disconnected } from '../lib/account'
import { errorMessage } from '../lib/api'
import { copyText } from '../lib/clipboard'
import {
  cachedLists,
  fetchGroupLists,
  fetchGroups,
  fetchLists,
  type GroupSummary,
} from '../lib/lists'
import type { ListSummary } from '../lib/storage'
import { VISIBILITY, whoCanOpen } from '../lib/visibility'
import NoticeBox from '../ui/NoticeBox.vue'
import ListDetail from './ListDetail.vue'

const emit = defineEmits<{
  /** The site ended the connection: the popup goes back to "Connect this browser". */
  disconnected: []
}>()

const lists = ref<ListSummary[]>()
const loading = ref(true)
const groups = ref<GroupSummary[]>([])
const group = ref('')
const inGroup = ref<Record<string, ListSummary[]>>({})
const query = ref('')
/** The list being looked into. */
const opened = ref<ListSummary>()
const notice = ref<{ tone: 'info' | 'warning' | 'error'; text: string }>()

function failed(error: unknown) {
  if (error instanceof Disconnected) emit('disconnected')
  else notice.value = { tone: 'error', text: errorMessage(error) }
}

const chosenGroup = computed(() => groups.value.find((item) => item.code === group.value))
/** The lists of the chosen group, in its order, or all of the account's. */
const pool = computed(() => (group.value ? inGroup.value[group.value] : lists.value) ?? [])
const shown = computed(() => {
  const text = query.value.trim().toLowerCase()
  return pool.value.filter((list) => !text || list.title.toLowerCase().includes(text))
})
const searchable = computed(() => pool.value.length > 6 || query.value !== '')
const about = (list: ListSummary) =>
  `${list.linkCount} ${list.linkCount === 1 ? 'link' : 'links'} · ${VISIBILITY[list.visibility]}`

onMounted(async () => {
  lists.value = (await cachedLists()) ?? undefined
  try {
    lists.value = await fetchLists()
  } catch (error) {
    if (error instanceof Disconnected || !lists.value) failed(error)
    else
      notice.value = {
        tone: 'warning',
        text: `${errorMessage(error)} These are your lists as they were last time.`,
      }
  } finally {
    loading.value = false
  }
  groups.value = await fetchGroups().catch(() => []) // browsing works without them
})

watch(group, async (code) => {
  query.value = ''
  notice.value = undefined
  if (!code || inGroup.value[code]) return
  try {
    inGroup.value = { ...inGroup.value, [code]: await fetchGroupLists(code) }
  } catch (error) {
    group.value = ''
    failed(error)
  }
})

// Copying a group's link changes nothing about who can open it; say who can.
async function copyGroupLink() {
  const item = chosenGroup.value
  if (!item) return
  try {
    await copyText(item.url)
    notice.value = {
      tone: 'info',
      text: `Group link copied. ${whoCanOpen(item.visibility, 'group', item.canSet)}`,
    }
  } catch {
    notice.value = { tone: 'error', text: "The browser didn't allow copying the link." }
  }
}

/** A list changed in its detail (who can open it): show it so everywhere here. */
function changed(list: ListSummary) {
  const swap = (other: ListSummary) => (other.code === list.code ? list : other)
  lists.value = lists.value?.map(swap)
  inGroup.value = Object.fromEntries(
    Object.entries(inGroup.value).map(([code, members]) => [code, members.map(swap)]),
  )
  opened.value = list
}
</script>

<template>
  <ListDetail
    v-if="opened"
    :list="opened"
    :groups="groups"
    @back="opened = undefined"
    @changed="changed"
    @disconnected="emit('disconnected')"
  />
  <section v-else class="browse" aria-label="My lists">
    <NoticeBox v-if="notice" :tone="notice.tone">{{ notice.text }}</NoticeBox>

    <div v-if="groups.length" class="ll-field">
      <label for="browse-group" class="ll-visually-hidden">Show lists from</label>
      <select id="browse-group" v-model="group" class="ll-input">
        <option value="">All my lists</option>
        <option v-for="item in groups" :key="item.code" :value="item.code">
          Group: {{ item.title }}
        </option>
      </select>
    </div>
    <div v-if="chosenGroup" class="browse__group">
      <p class="ll-muted">
        {{ chosenGroup.listCount }} {{ chosenGroup.listCount === 1 ? 'list' : 'lists' }} ·
        {{ VISIBILITY[chosenGroup.visibility] }}
      </p>
      <div class="ll-row">
        <button type="button" class="ll-button ll-button--tonal" @click="copyGroupLink">
          Copy group link
        </button>
        <a
          class="ll-button ll-button--text"
          :href="chosenGroup.url"
          target="_blank"
          rel="noreferrer"
        >
          Open the group
        </a>
      </div>
    </div>

    <div v-if="searchable" class="ll-field">
      <label for="browse-search" class="ll-visually-hidden">Search lists</label>
      <input
        id="browse-search"
        v-model="query"
        class="ll-input"
        type="search"
        placeholder="Search lists"
        autocomplete="off"
      />
    </div>

    <p v-if="loading && !shown.length" class="ll-muted" aria-busy="true">Loading your lists…</p>
    <p v-else-if="!shown.length" class="ll-muted">
      {{
        query
          ? 'No list matches.'
          : group
            ? 'This group shows you no lists.'
            : 'You have no lists yet. Save a page to make one.'
      }}
    </p>
    <ul v-else class="browse__lists">
      <li v-for="list in shown" :key="list.code">
        <button type="button" class="browse__list" @click="opened = list">
          <span class="browse__text">
            <span class="browse__title">{{ list.title }}</span>
            <span class="browse__about ll-muted">{{ about(list) }}</span>
          </span>
          <span aria-hidden="true">›</span>
        </button>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.browse {
  display: grid;
  gap: 12px;
  min-width: 0;
}
.browse__group {
  display: grid;
  gap: 8px;
}
.browse__lists {
  max-height: 260px;
  margin: 0;
  padding: 4px;
  overflow-y: auto;
  border: 1px solid var(--ll-outline-variant);
  border-radius: var(--ll-radius);
  background: var(--ll-surface);
  list-style: none;
}
.browse__list {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  padding: 6px 8px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.browse__list:hover {
  background: var(--ll-primary-container);
  color: var(--ll-on-primary-container);
}
.browse__list:hover .browse__about {
  color: inherit;
}
.browse__text {
  display: grid;
  min-width: 0;
}
.browse__title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}
.browse__about {
  font-size: 12px;
}
</style>
