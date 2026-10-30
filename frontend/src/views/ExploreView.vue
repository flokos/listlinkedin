<script setup lang="ts">
// Explore: the public directory of lists and groups (task 8.2). Only public ones are listed;
// the server filters them. Search words, tags, sort and the tab are in the address.
import { mdiCompassOutline, mdiMagnify, mdiRefresh, mdiTagOffOutline } from '@mdi/js'
import { computed, onMounted, onScopeDispose, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  directory,
  errorMessage,
  type GroupDetail,
  type ListDetail,
  popularTags,
  type TagCount,
} from '../api'
import DirectoryCard from '../components/DirectoryCard.vue'
import LiveRegion from '../components/LiveRegion.vue'
import StatePanel from '../components/StatePanel.vue'
import { useSession } from '../composables/useSession'
import {
  effectiveSort,
  exploreQuery,
  type ExploreSort,
  type ExploreState,
  orderingFor,
  parseExplore,
  sortOptions,
} from '../utils/explore'

const route = useRoute()
const router = useRouter()
const session = useSession()

const state = computed(() => parseExplore(route.query))
const noun = computed(() => (state.value.kind === 'groups' ? 'groups' : 'lists'))
const filtered = computed(() => Boolean(state.value.q || state.value.tags.length))

function go(changes: Partial<ExploreState>, { replace = false } = {}) {
  const query = exploreQuery({ ...state.value, ...changes })
  void router[replace ? 'replace' : 'push']({ name: 'explore', query })
}

// Search words: applied as you type (after a pause, without a history entry each time) or at
// once with Enter.
const words = ref(state.value.q)
let typing: ReturnType<typeof setTimeout> | undefined
watch(
  () => state.value.q,
  (q) => {
    if (q !== words.value.trim()) words.value = q
  },
)
function typed(value: string | null) {
  words.value = value ?? ''
  clearTimeout(typing)
  typing = setTimeout(() => applyWords({ replace: true }), 400)
}
function applyWords({ replace = false } = {}) {
  clearTimeout(typing)
  const q = words.value.trim()
  if (q !== state.value.q) go({ q }, { replace })
}
onScopeDispose(() => clearTimeout(typing))

function toggleTag(tag: string) {
  const tags = state.value.tags
  go({ tags: tags.includes(tag) ? tags.filter((t) => t !== tag) : [...tags, tag] })
}

// Results, one page of 20 at a time.
const items = ref<(ListDetail | GroupDetail)[]>([])
const count = ref(0)
const page = ref(1)
const hasMore = ref(false)
const status = ref<'loading' | 'ready' | 'error'>('loading')
const loadError = ref('')
const loadingMore = ref(false)
const moreError = ref('')
const announcement = ref<{ text: string } | null>(null)
let controller: AbortController | undefined

function fetchPage(number: number) {
  controller?.abort()
  controller = new AbortController()
  const query = {
    q: state.value.q,
    tags: state.value.tags,
    ordering: orderingFor(state.value),
    page: number,
  }
  return state.value.kind === 'groups'
    ? directory('groups', query, controller.signal)
    : directory('lists', query, controller.signal)
}

const aborted = (error: unknown) => error instanceof DOMException && error.name === 'AbortError'

async function load() {
  status.value = 'loading'
  moreError.value = ''
  try {
    const result = await fetchPage(1)
    items.value = result.results
    count.value = result.count
    page.value = 1
    hasMore.value = Boolean(result.next)
    status.value = 'ready'
    const what = `${result.count} ${result.count === 1 ? noun.value.slice(0, -1) : noun.value}`
    announcement.value = { text: result.count ? `${what} found` : `No ${noun.value} found` }
  } catch (error) {
    if (aborted(error)) return
    loadError.value = errorMessage(error)
    status.value = 'error'
  }
}

async function loadMore() {
  loadingMore.value = true
  moreError.value = ''
  try {
    const result = await fetchPage(page.value + 1)
    const known = new Set(items.value.map((item) => item.id))
    items.value = [...items.value, ...result.results.filter((item) => !known.has(item.id))]
    page.value += 1
    hasMore.value = Boolean(result.next)
    announcement.value = { text: `Showing ${items.value.length} of ${count.value}` }
  } catch (error) {
    if (!aborted(error)) moreError.value = errorMessage(error)
  } finally {
    loadingMore.value = false
  }
}

watch(
  () => route.query,
  () => {
    if (route.name === 'explore') void load()
  },
  { immediate: true },
)
onScopeDispose(() => controller?.abort())

// Popular tags across public lists and groups, plus the chosen ones.
const popular = ref<TagCount[]>([])
onMounted(async () => {
  try {
    popular.value = await popularTags()
  } catch {
    // Optional: tags on the cards still filter.
  }
})
const tagChoices = computed(() => {
  const chosen = state.value.tags
  const others = popular.value.map((t) => t.tag).filter((tag) => !chosen.includes(tag))
  return [...chosen, ...others.slice(0, 12)]
})

const sorts = computed(() => sortOptions(Boolean(state.value.q)))
const sort = computed({
  get: () => effectiveSort(state.value),
  set: (value: ExploreSort) => go({ sort: value }),
})
</script>

<template>
  <div class="ll-content py-6 py-md-10">
    <h1 class="text-headline-large">Explore</h1>
    <p class="text-body-large text-medium-emphasis ll-reading mt-1 mb-6">
      Public lists and groups that people share with everyone.
    </p>

    <v-tabs
      :model-value="state.kind"
      color="primary"
      class="mb-4"
      aria-label="What to explore"
      @update:model-value="(kind) => go({ kind: kind === 'groups' ? 'groups' : 'lists' })"
    >
      <v-tab value="lists">Lists</v-tab>
      <v-tab value="groups">Groups</v-tab>
    </v-tabs>

    <form role="search" class="d-flex flex-wrap ga-3 align-start" @submit.prevent="applyWords()">
      <v-text-field
        :model-value="words"
        type="search"
        :label="`Search public ${noun}`"
        :prepend-inner-icon="mdiMagnify"
        maxlength="200"
        clearable
        hide-details
        class="ll-explore__search"
        @update:model-value="typed"
      />
      <v-select
        v-model="sort"
        :items="sorts"
        label="Sort by"
        hide-details
        class="ll-explore__sort"
      />
    </form>

    <div v-if="tagChoices.length" class="mt-4">
      <h2 id="explore-tags" class="text-label-large text-medium-emphasis mb-2">Tags</h2>
      <ul class="ll-explore__tags" aria-labelledby="explore-tags">
        <li v-for="tag in tagChoices" :key="tag">
          <v-chip
            tag="button"
            type="button"
            :variant="state.tags.includes(tag) ? 'flat' : 'outlined'"
            :color="state.tags.includes(tag) ? 'primary' : undefined"
            :aria-pressed="state.tags.includes(tag)"
            @click="toggleTag(tag)"
            >{{ tag }}</v-chip
          >
        </li>
      </ul>
    </div>

    <LiveRegion :message="announcement" />

    <div class="mt-6">
      <v-progress-linear
        v-if="status === 'loading'"
        indeterminate
        color="primary"
        :aria-label="`Loading public ${noun}`"
      />
      <v-alert v-if="status === 'error'" type="error" :text="loadError">
        <template #append>
          <v-btn variant="text" :prepend-icon="mdiRefresh" @click="load">Try again</v-btn>
        </template>
      </v-alert>
      <template v-else-if="status === 'ready' || items.length">
        <StatePanel
          v-if="!items.length && filtered"
          :icon="mdiTagOffOutline"
          :title="`No ${noun} match`"
          :text="
            state.tags.length
              ? 'Try other words, or remove a tag.'
              : 'Try other or fewer words. Partial words match names.'
          "
        >
          <template #actions>
            <v-btn color="primary" variant="tonal" @click="go({ q: '', tags: [] })"
              >Clear search</v-btn
            >
          </template>
        </StatePanel>
        <StatePanel
          v-else-if="!items.length"
          :icon="mdiCompassOutline"
          :title="`No public ${noun} yet`"
          :text="`When people make ${noun === 'groups' ? 'a group' : 'a list'} public, it shows up here.`"
        >
          <template #actions>
            <v-btn
              v-if="session.isSignedIn.value"
              color="primary"
              :to="{ name: noun === 'groups' ? 'groups' : 'saved-lists' }"
              >{{ noun === 'groups' ? 'Your groups' : 'Your lists' }}</v-btn
            >
            <v-btn v-else color="primary" :to="{ name: 'signup' }">Create an account</v-btn>
          </template>
        </StatePanel>
        <template v-else>
          <p class="text-body-medium text-medium-emphasis mb-3" aria-hidden="true">
            {{ count }} {{ count === 1 ? noun.slice(0, -1) : noun }}
          </p>
          <ul class="ll-explore__results pa-0" :aria-label="`Public ${noun}`">
            <li v-for="item in items" :key="item.id">
              <DirectoryCard :item="item" :chosen-tags="state.tags" @tag="toggleTag" />
            </li>
          </ul>
          <div v-if="hasMore || moreError" class="d-flex flex-column align-center ga-2 mt-6">
            <p v-if="moreError" class="text-body-medium text-error">{{ moreError }}</p>
            <v-btn variant="tonal" color="primary" :loading="loadingMore" @click="loadMore"
              >Show more</v-btn
            >
          </div>
        </template>
      </template>
    </div>
  </div>
</template>

<style scoped>
.ll-explore__search {
  flex: 1 1 280px;
}
.ll-explore__sort {
  flex: 0 1 200px;
  min-width: 180px;
}
.ll-explore__tags {
  list-style: none;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.ll-explore__results {
  list-style: none;
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 380px), 1fr));
}
</style>
