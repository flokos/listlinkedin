<script setup lang="ts">
// The popup of a connected browser: save the page you are on into one of your lists.
import { computed, onMounted, ref, watch } from 'vue'

import { Disconnected } from '../lib/account'
import { errorMessage } from '../lib/api'
import { copyText } from '../lib/clipboard'
import {
  byLastUse,
  cachedLists,
  createList,
  fetchGroupLists,
  fetchGroups,
  fetchLists,
  type GroupSummary,
  LINKS_PER_LIST,
  savePage,
} from '../lib/lists'
import { type PageToSave, pageToSave, whyNotSaveable } from '../lib/pages'
import { getNewListVisibility, getRecent, type ListSummary, type Visibility } from '../lib/storage'
import { whoCanOpen } from '../lib/visibility'
import NewListAccess from '../ui/NewListAccess.vue'
import NoticeBox from '../ui/NoticeBox.vue'
import ListPicker from './ListPicker.vue'

const emit = defineEmits<{
  /** The site ended the connection: the popup goes back to "Connect this browser". */
  disconnected: []
}>()

const page = ref<PageToSave | null>()
const title = ref('')
const blocked = computed(() => (page.value === undefined ? null : whyNotSaveable(page.value?.url)))

const lists = ref<ListSummary[]>()
const loading = ref(true)
const recent = ref<string[]>([])
const groups = ref<GroupSummary[]>([])
const group = ref('')
const inGroup = ref<Record<string, ListSummary[]>>({})
const query = ref('')
const selected = ref('')

const busy = ref(false)
const notice = ref<{ tone: 'info' | 'warning' | 'error'; text: string }>()
const saved = ref<{ list: ListSummary; shortUrl: string | null }>()

function failed(error: unknown) {
  if (error instanceof Disconnected) emit('disconnected')
  else notice.value = { tone: 'error', text: errorMessage(error) }
}

/** The lists of the chosen group, or all of the account's. */
const pool = computed(() => (group.value ? inGroup.value[group.value] : lists.value) ?? [])
const editable = computed(() => pool.value.filter((list) => list.canEdit))
const choices = computed(() => {
  const text = query.value.trim().toLowerCase()
  const found = editable.value.filter((list) => !text || list.title.toLowerCase().includes(text))
  // A group has its own order. Otherwise the lists saved to last come first, in that order,
  // and the rest stay as the site sorts them.
  return group.value ? found : byLastUse(found, recent.value)
})
const known = computed(() => [...(lists.value ?? []), ...Object.values(inGroup.value).flat()])
const target = computed(() => known.value.find((list) => list.code === selected.value))

async function loadLists() {
  loading.value = true
  try {
    lists.value = await fetchLists()
    if (notice.value?.tone === 'warning') notice.value = undefined
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
}

onMounted(async () => {
  page.value = await pageToSave().catch(() => null)
  title.value = page.value?.title ?? ''
  recent.value = await getRecent()
  newAccess.value = await getNewListVisibility()
  lists.value = (await cachedLists()) ?? undefined
  // Offer the list saved to last, if it can still take a link.
  const last = lists.value?.find((list) => list.code === recent.value[0])
  if (last?.canEdit && last.linkCount < LINKS_PER_LIST) selected.value = last.code
  await loadLists()
  groups.value = await fetchGroups().catch(() => []) // the picker works without them
})

watch(group, async (code) => {
  query.value = ''
  if (!code || inGroup.value[code]) return
  try {
    inGroup.value = { ...inGroup.value, [code]: await fetchGroupLists(code) }
  } catch (error) {
    group.value = ''
    failed(error)
  }
})

// A new list, made here and chosen at once.
const creating = ref(false)
const newTitle = ref('')
/** Who can open the new list: the user's answer here, starting from the one given last. */
const newAccess = ref<Visibility>('private')
let createKey = crypto.randomUUID()
async function create() {
  const name = newTitle.value.trim()
  if (!name) return
  busy.value = true
  notice.value = undefined
  try {
    const list = await createList(name, createKey, newAccess.value)
    lists.value = [list, ...(lists.value ?? []).filter((other) => other.code !== list.code)]
    group.value = ''
    query.value = ''
    selected.value = list.code
    creating.value = false
    newTitle.value = ''
    createKey = crypto.randomUUID()
  } catch (error) {
    failed(error)
  } finally {
    busy.value = false
  }
}

// One key per page and list: saving again after a lost answer returns the same link.
const keys = new Map<string, string>()
function keyFor(list: string, url: string): string {
  const id = `${list}\n${url}`
  if (!keys.has(id)) keys.set(id, crypto.randomUUID())
  return keys.get(id)!
}

async function save() {
  const list = target.value
  if (!page.value || blocked.value || !list) return
  busy.value = true
  notice.value = undefined
  try {
    const { url } = page.value
    const outcome = await savePage(list.code, { url, title: title.value }, keyFor(list.code, url))
    if (outcome.saved) saved.value = { list, shortUrl: outcome.link.short_url }
    else notice.value = { tone: 'info', text: outcome.reason }
  } catch (error) {
    failed(error)
  } finally {
    busy.value = false
  }
}

// The short link opens the page through the site, for whoever may open the list: copying it
// changes nothing about who that is.
const copied = ref('')
async function copyShortLink() {
  if (!saved.value?.shortUrl) return
  const { list, shortUrl } = saved.value
  try {
    await copyText(shortUrl)
    copied.value = `Short link copied. ${whoCanOpen(list.visibility, 'list', list.canSet)}`
  } catch {
    copied.value = `The browser didn't allow copying. The short link is ${shortUrl}`
  }
}

function another() {
  saved.value = undefined
  copied.value = ''
  selected.value = ''
  void loadLists() // the list just saved to has one more link
}
</script>

<template>
  <section v-if="saved" class="save">
    <NoticeBox tone="success">
      Saved to <strong>{{ saved.list.title }}</strong
      >.
    </NoticeBox>
    <div class="ll-row">
      <a class="ll-button" :href="saved.list.url" target="_blank" rel="noreferrer">Open the list</a>
      <button
        v-if="saved.shortUrl"
        type="button"
        class="ll-button ll-button--tonal"
        @click="copyShortLink"
      >
        Copy short link
      </button>
      <button type="button" class="ll-button ll-button--text" @click="another">
        Save to another list
      </button>
    </div>
    <!-- Always there, so that a screen reader hears it fill. -->
    <p class="ll-muted save__copied" aria-live="polite">{{ copied }}</p>
  </section>

  <form v-else class="save" novalidate @submit.prevent="save">
    <NoticeBox v-if="notice" :tone="notice.tone">{{ notice.text }}</NoticeBox>

    <NoticeBox v-if="blocked" tone="info">{{ blocked }}</NoticeBox>
    <template v-else-if="page">
      <div class="ll-field">
        <label for="save-title">Title</label>
        <input
          id="save-title"
          v-model="title"
          class="ll-input"
          maxlength="255"
          autocomplete="off"
          placeholder="The page's own title"
        />
      </div>
      <p class="save__url ll-muted" :title="page.url">{{ page.url }}</p>
    </template>

    <template v-if="page !== undefined && !blocked">
      <ListPicker
        v-model="selected"
        v-model:query="query"
        v-model:group="group"
        :lists="choices"
        :total="editable.length"
        :groups="groups"
        :loading="loading"
      />

      <div v-if="creating" class="ll-field">
        <label for="save-new-list">New list's name</label>
        <div class="save__new">
          <input
            id="save-new-list"
            v-model="newTitle"
            class="ll-input"
            maxlength="255"
            autocomplete="off"
            @keydown.enter.prevent="create"
          />
          <button
            type="button"
            class="ll-button ll-button--tonal"
            :disabled="busy || !newTitle.trim()"
            @click="create"
          >
            Create
          </button>
        </div>
      </div>
      <NewListAccess v-if="creating" id="save-new-access" v-model="newAccess" :disabled="busy" />
      <div class="ll-row save__actions">
        <button type="submit" class="ll-button" :disabled="busy || !target">Save</button>
        <button
          v-if="!creating"
          type="button"
          class="ll-button ll-button--text"
          @click="creating = true"
        >
          New list
        </button>
      </div>
    </template>
  </form>
</template>

<style scoped>
.save {
  display: grid;
  gap: 12px;
  min-width: 0;
}
.save__url {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}
.save__copied {
  font-size: 12px;
  overflow-wrap: anywhere;
}
.save__new {
  display: flex;
  gap: 8px;
}
.save__actions {
  justify-content: space-between;
}
</style>
