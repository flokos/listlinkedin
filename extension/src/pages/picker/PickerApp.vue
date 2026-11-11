<script setup lang="ts">
// Saving several pages at once: pick from the open tabs or from the browsing history, choose
// a list (or a new one), and save them as one change.
//
// The tabs and the history are read here, inside the browser, and only after the user
// allowed it for this (src/lib/permissions.ts). Nothing is sent but the pages they tick.
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { Disconnected } from '../../lib/account'
import { errorMessage } from '../../lib/api'
import { type BatchResult, BatchStopped, describe, saveMany } from '../../lib/batch'
import { byLastUse, cachedLists, createList, fetchLists, LINKS_PER_LIST } from '../../lib/lists'
import type { PageToSave } from '../../lib/pages'
import { allow, isAllowed, type Optional, WHAT } from '../../lib/permissions'
import { historyPages, openTabs } from '../../lib/sources'
import {
  type Connection,
  getConnection,
  getNewListVisibility,
  getRecent,
  type ListSummary,
  onConnectionChange,
  type Visibility,
} from '../../lib/storage'
import BrandMark from '../../ui/BrandMark.vue'
import ConnectPrompt from '../../ui/ConnectPrompt.vue'
import NewListAccess from '../../ui/NewListAccess.vue'
import NoticeBox from '../../ui/NoticeBox.vue'

const SOURCES: { name: Optional; label: string }[] = [
  { name: 'tabs', label: 'Open tabs' },
  { name: 'history', label: 'History' },
]
const NEW_LIST = '+new'

const connection = ref<Connection | null>()
const asked = new URLSearchParams(window.location.search).get('source')
const source = ref<Optional>(asked === 'history' ? 'history' : 'tabs')
/** Whether the browser lets the extension read the chosen source: undefined while asking. */
const allowed = ref<boolean>()
const pages = ref<PageToSave[]>([])
const loading = ref(false)
const query = ref('')
const picked = ref<string[]>([])

const lists = ref<ListSummary[]>([])
const target = ref('')
const newTitle = ref('')
/** Who can open the new list: the user's answer here, starting from the one given last. */
const newAccess = ref<Visibility>('private')
const busy = ref(false)
const problem = ref('')
const done = ref<{ result: BatchResult; list: ListSummary; stopped?: string }>()
let stop = () => {}

function failed(error: unknown) {
  if (error instanceof Disconnected) connection.value = null
  else problem.value = errorMessage(error)
}

async function loadPages() {
  loading.value = true
  problem.value = ''
  try {
    pages.value = source.value === 'tabs' ? await openTabs() : await historyPages(query.value)
    // What was ticked stays ticked while it is still offered.
    const offered = new Set(pages.value.map((page) => page.url))
    picked.value = picked.value.filter((url) => offered.has(url))
  } catch {
    problem.value = `The browser didn't let the extension read ${WHAT[source.value]}.`
    pages.value = []
  } finally {
    loading.value = false
  }
}

async function show(next: Optional) {
  source.value = next
  query.value = ''
  picked.value = []
  pages.value = []
  done.value = undefined
  allowed.value = undefined
  allowed.value = await isAllowed(next).catch(() => false)
  if (allowed.value) await loadPages()
}

// Browsers only show their question from a click, so this is the button's own handler.
async function ask() {
  problem.value = ''
  allowed.value = await allow(source.value).catch(() => false)
  if (allowed.value) await loadPages()
  else problem.value = `Without it the extension can't show ${WHAT[source.value]}.`
}

async function loadLists() {
  const recent = await getRecent()
  const offer = (all: ListSummary[]) => {
    lists.value = byLastUse(
      all.filter((list) => list.canEdit),
      recent,
    )
    // The list saved to last, unless the user has chosen already.
    if (!target.value && lists.value[0]) target.value = lists.value[0].code
  }
  offer((await cachedLists()) ?? [])
  try {
    offer(await fetchLists())
  } catch (error) {
    failed(error)
  }
  if (!target.value) target.value = NEW_LIST // an account without a list to save to
}

onMounted(async () => {
  newAccess.value = await getNewListVisibility()
  connection.value = await getConnection()
  stop = onConnectionChange((next) => (connection.value = next))
})
onBeforeUnmount(() => stop())
watch(
  connection,
  (now, before) => {
    if (now && !before) void Promise.all([loadLists(), show(source.value)])
  },
  { immediate: true },
)

// The history is searched by the browser; a pause in typing starts it.
let typing: ReturnType<typeof setTimeout> | undefined
watch(query, () => {
  if (source.value !== 'history') return
  clearTimeout(typing)
  typing = setTimeout(() => void loadPages(), 250)
})

const shown = computed(() => {
  const text = source.value === 'tabs' ? query.value.trim().toLowerCase() : ''
  if (!text) return pages.value
  return pages.value.filter(
    (page) => page.title.toLowerCase().includes(text) || page.url.toLowerCase().includes(text),
  )
})
const allPicked = computed(
  () => shown.value.length > 0 && shown.value.every((page) => picked.value.includes(page.url)),
)
function toggleAll() {
  const here = new Set(shown.value.map((page) => page.url))
  picked.value = allPicked.value
    ? picked.value.filter((url) => !here.has(url))
    : [...new Set([...picked.value, ...here])]
}

const chosen = computed(() => lists.value.find((list) => list.code === target.value))
const room = computed(() =>
  chosen.value ? LINKS_PER_LIST - chosen.value.linkCount : LINKS_PER_LIST,
)
const ready = computed(
  () =>
    picked.value.length > 0 &&
    (target.value === NEW_LIST ? newTitle.value.trim() !== '' : chosen.value !== undefined),
)
const about = (list: ListSummary) =>
  list.linkCount >= LINKS_PER_LIST ? `${list.title} (full)` : list.title

let createKey = crypto.randomUUID()
async function save() {
  if (!ready.value) return
  busy.value = true
  problem.value = ''
  try {
    let list = chosen.value
    if (target.value === NEW_LIST) {
      list = await createList(newTitle.value.trim(), createKey, newAccess.value)
      createKey = crypto.randomUUID()
      lists.value = [list, ...lists.value]
      target.value = list.code
      newTitle.value = ''
    }
    if (!list) return
    // In the order shown, not the order ticked.
    const wanted = pages.value.filter((page) => picked.value.includes(page.url))
    try {
      done.value = { result: await saveMany(list.code, wanted), list }
    } catch (error) {
      if (!(error instanceof BatchStopped)) throw error
      if (error.reason instanceof Disconnected) throw error.reason
      done.value = { result: error.result, list, stopped: errorMessage(error.reason) }
    }
    picked.value = []
  } catch (error) {
    failed(error)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main class="ll-page picker">
    <BrandMark :size="32" />
    <h1>Save several pages</h1>

    <p v-if="connection === undefined" class="ll-muted" aria-busy="true">Loading…</p>
    <section v-else-if="connection === null" class="ll-card picker__card">
      <h2>First, connect this browser</h2>
      <ConnectPrompt />
    </section>
    <template v-else>
      <div class="picker__sources" role="group" aria-label="Pick from">
        <button
          v-for="item in SOURCES"
          :key="item.name"
          type="button"
          class="picker__source"
          :aria-pressed="source === item.name"
          @click="show(item.name)"
        >
          {{ item.label }}
        </button>
      </div>

      <NoticeBox v-if="problem" tone="error">{{ problem }}</NoticeBox>
      <NoticeBox v-if="done" :tone="done.stopped ? 'warning' : 'success'">
        {{ describe(done.result) }}
        <template v-if="done.stopped"> {{ done.stopped }}</template>
        <a :href="done.list.url" target="_blank" rel="noreferrer">Open “{{ done.list.title }}”</a>
      </NoticeBox>

      <section v-if="allowed === false" class="ll-card picker__card">
        <p>
          To pick from {{ WHAT[source] }}, the extension needs your permission to read them. They
          are read here, in your browser: only the pages you tick are sent to listlinkedin. You can
          take the permission back in the extension's options.
        </p>
        <div>
          <button type="button" class="ll-button" @click="ask">
            Allow reading {{ WHAT[source] }}
          </button>
        </div>
      </section>

      <form v-else-if="allowed" class="picker__form" novalidate @submit.prevent="save">
        <div class="ll-field">
          <label for="picker-search">
            {{ source === 'history' ? 'Search your history' : 'Search the open tabs' }}
          </label>
          <input
            id="picker-search"
            v-model="query"
            class="ll-input"
            type="search"
            autocomplete="off"
          />
        </div>

        <p v-if="loading && !shown.length" class="ll-muted" aria-busy="true">Loading…</p>
        <p v-else-if="!shown.length" class="ll-muted">
          {{
            query
              ? 'Nothing matches.'
              : source === 'tabs'
                ? 'No open tab has a page that can be saved.'
                : 'Your history has no page that can be saved.'
          }}
        </p>
        <fieldset v-else class="picker__pages">
          <legend class="ll-visually-hidden">Pages</legend>
          <label class="picker__all">
            <input type="checkbox" :checked="allPicked" @change="toggleAll" />
            <span>Select all {{ shown.length }}</span>
          </label>
          <ul>
            <li v-for="page in shown" :key="page.url">
              <label class="picker__page">
                <input v-model="picked" type="checkbox" :value="page.url" />
                <span class="picker__text">
                  <span class="picker__title">{{ page.title || page.url }}</span>
                  <span class="picker__url ll-muted">{{ page.url }}</span>
                </span>
              </label>
            </li>
          </ul>
        </fieldset>

        <div class="ll-field">
          <label for="picker-list">Save to</label>
          <select id="picker-list" v-model="target" class="ll-input" :disabled="busy">
            <option v-for="list in lists" :key="list.code" :value="list.code">
              {{ about(list) }}
            </option>
            <option :value="NEW_LIST">A new list…</option>
          </select>
        </div>
        <div v-if="target === NEW_LIST" class="ll-field">
          <label for="picker-new-list">New list's name</label>
          <input
            id="picker-new-list"
            v-model="newTitle"
            class="ll-input"
            maxlength="255"
            autocomplete="off"
          />
        </div>
        <NewListAccess
          v-if="target === NEW_LIST"
          id="picker-new-access"
          v-model="newAccess"
          :disabled="busy"
        />
        <p v-if="picked.length > room" class="ll-muted" role="note">
          {{ picked.length }} pages are ticked and this list has room for {{ room }}: the first
          {{ room }} that aren't in it yet will be saved.
        </p>

        <div class="ll-row">
          <button type="submit" class="ll-button" :disabled="busy || !ready">
            {{
              picked.length
                ? `Save ${picked.length} ${picked.length === 1 ? 'page' : 'pages'}`
                : 'Save'
            }}
          </button>
          <span class="ll-muted">{{ connection.email }}</span>
        </div>
      </form>
    </template>
  </main>
</template>

<style scoped>
.picker {
  max-width: 720px;
}
.picker__card,
.picker__form {
  display: grid;
  gap: 12px;
}
.picker__sources {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  max-width: 320px;
  padding: 3px;
  border-radius: 999px;
  background: var(--ll-outline-variant);
}
.picker__source {
  min-height: 32px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--ll-on-surface);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}
.picker__source[aria-pressed='true'] {
  background: var(--ll-surface);
  color: var(--ll-primary);
}
.picker__pages {
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 1px solid var(--ll-outline-variant);
  border-radius: var(--ll-radius);
  background: var(--ll-surface);
}
.picker__pages ul {
  max-height: 46vh;
  margin: 0;
  padding: 4px;
  overflow-y: auto;
  list-style: none;
}
.picker__all,
.picker__page {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
}
.picker__all {
  padding: 8px 12px;
  border-bottom: 1px solid var(--ll-outline-variant);
  font-weight: 600;
}
.picker__page:has(input:checked) {
  background: var(--ll-primary-container);
  color: var(--ll-on-primary-container);
}
.picker__page:has(input:checked) .picker__url {
  color: inherit;
}
.picker__pages input {
  margin: 3px 0 0;
  accent-color: var(--ll-primary);
}
.picker__text {
  display: grid;
  min-width: 0;
}
.picker__title,
.picker__url {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.picker__title {
  font-weight: 600;
}
.picker__url {
  font-size: 12px;
}
</style>
