<script setup lang="ts">
// One list, looked into from "My lists": its links, its address to copy or open, who can open
// it (and changing that, for its owner), and adding it to a group.
//
// Copying a link never changes who can open the list: that only happens when the user picks
// another answer under "Who can open it" and chooses Change (invariant 2). What this account
// may do comes from the server (`canSet`, `canAddList`), and the server decides again on
// every request.
import { computed, onMounted, ref } from 'vue'

import { Disconnected } from '../lib/account'
import { errorMessage } from '../lib/api'
import { copyText } from '../lib/clipboard'
import {
  addToGroup,
  fetchLinks,
  type GroupSummary,
  type LinkSummary,
  setVisibility,
} from '../lib/lists'
import type { ListSummary, Visibility } from '../lib/storage'
import { VISIBILITIES, VISIBILITY, whoCanOpen } from '../lib/visibility'
import NoticeBox from '../ui/NoticeBox.vue'

const props = defineProps<{
  list: ListSummary
  /** The account's groups: the ones it may add lists to are offered. */
  groups: GroupSummary[]
}>()
const emit = defineEmits<{
  back: []
  /** The list as the site has it now, after a change made here. */
  changed: [list: ListSummary]
  disconnected: []
}>()

const links = ref<LinkSummary[]>()
const linksError = ref('')
const note = ref<{ tone: 'info' | 'success' | 'error'; text: string }>()
const busy = ref(false)

function failed(error: unknown) {
  if (error instanceof Disconnected) emit('disconnected')
  else note.value = { tone: 'error', text: errorMessage(error) }
}

const who = computed(() => whoCanOpen(props.list.visibility, 'list', props.list.canSet))
const count = computed(
  () => `${props.list.linkCount} ${props.list.linkCount === 1 ? 'link' : 'links'}`,
)

onMounted(async () => {
  try {
    links.value = await fetchLinks(props.list.code)
  } catch (error) {
    if (error instanceof Disconnected) emit('disconnected')
    else linksError.value = errorMessage(error)
  }
})

/** Only web addresses become links here; the site stores no others. */
const isWeb = (url: string) => /^https?:\/\//i.test(url)

async function copy(text: string, what: string) {
  try {
    await copyText(text)
    note.value = { tone: 'info', text: `${what} copied. ${who.value}` }
  } catch {
    note.value = { tone: 'error', text: `The browser didn't allow copying. The address is ${text}` }
  }
}

// Who can open it: changed only by choosing another answer and then "Change".
const choice = ref<Visibility>(props.list.visibility)
async function changeVisibility() {
  if (choice.value === props.list.visibility) return
  busy.value = true
  note.value = undefined
  try {
    const list = await setVisibility(props.list.code, choice.value)
    emit('changed', list)
    note.value = {
      tone: 'success',
      text: `Changed. ${whoCanOpen(list.visibility, 'list', list.canSet)}`,
    }
  } catch (error) {
    choice.value = props.list.visibility // nothing changed
    failed(error)
  } finally {
    busy.value = false
  }
}

const addable = computed(() => props.groups.filter((group) => group.canAddList))
const target = ref('')
async function add() {
  const group = addable.value.find((item) => item.code === target.value)
  if (!group) return
  busy.value = true
  note.value = undefined
  try {
    const outcome = await addToGroup(group.code, props.list.code)
    note.value = outcome.added
      ? { tone: 'success', text: `Added to the group “${group.title}”.` }
      : { tone: 'info', text: outcome.reason }
    if (outcome.added) target.value = ''
  } catch (error) {
    failed(error)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="detail" aria-labelledby="detail-title">
    <div>
      <button type="button" class="ll-button ll-button--text detail__back" @click="emit('back')">
        <span aria-hidden="true">‹</span> All lists
      </button>
    </div>
    <div>
      <h2 id="detail-title" class="detail__title">{{ list.title }}</h2>
      <p class="ll-muted">{{ count }} · {{ VISIBILITY[list.visibility] }}</p>
    </div>
    <div class="ll-row">
      <button type="button" class="ll-button" @click="copy(list.url, 'Link')">Copy link</button>
      <a class="ll-button ll-button--text" :href="list.url" target="_blank" rel="noreferrer">
        Open on listlinkedin
      </a>
    </div>
    <NoticeBox v-if="note" :tone="note.tone">{{ note.text }}</NoticeBox>

    <div v-if="list.canSet" class="ll-field">
      <label for="detail-visibility">Who can open it</label>
      <div class="detail__inline">
        <select id="detail-visibility" v-model="choice" class="ll-input" :disabled="busy">
          <option v-for="value in VISIBILITIES" :key="value" :value="value">
            {{ VISIBILITY[value] }}
          </option>
        </select>
        <button
          type="button"
          class="ll-button ll-button--tonal"
          :disabled="busy || choice === list.visibility"
          @click="changeVisibility"
        >
          Change
        </button>
      </div>
    </div>
    <p v-else class="ll-muted">{{ who }}</p>

    <div v-if="addable.length" class="ll-field">
      <label for="detail-group">Add to a group</label>
      <div class="detail__inline">
        <select id="detail-group" v-model="target" class="ll-input" :disabled="busy">
          <option value="" disabled>Choose a group</option>
          <option v-for="group in addable" :key="group.code" :value="group.code">
            {{ group.title }}
          </option>
        </select>
        <button
          type="button"
          class="ll-button ll-button--tonal"
          :disabled="busy || !target"
          @click="add"
        >
          Add
        </button>
      </div>
    </div>

    <div class="detail__links-block">
      <h3 class="ll-label">Links</h3>
      <NoticeBox v-if="linksError" tone="error">{{ linksError }}</NoticeBox>
      <p v-else-if="!links" class="ll-muted" aria-busy="true">Loading the links…</p>
      <p v-else-if="!links.length" class="ll-muted">This list has no links yet.</p>
      <ul v-else class="detail__links">
        <li v-for="link in links" :key="link.id" class="detail__link">
          <span class="detail__link-text">
            <a
              v-if="isWeb(link.url)"
              class="detail__link-title"
              :href="link.url"
              target="_blank"
              rel="noreferrer"
            >
              {{ link.title }}
            </a>
            <span v-else class="detail__link-title">{{ link.title }}</span>
            <span class="detail__link-site ll-muted">{{ link.site }}</span>
          </span>
          <button
            v-if="link.shortUrl"
            type="button"
            class="ll-button ll-button--text detail__copy"
            title="Copy the short link"
            :aria-label="`Copy the short link of ${link.title}`"
            @click="copy(link.shortUrl, 'Short link')"
          >
            Copy
          </button>
        </li>
      </ul>
    </div>
  </section>
</template>

<style scoped>
.detail {
  display: grid;
  gap: 12px;
  min-width: 0;
}
.detail__back {
  min-height: 28px;
  padding: 0 4px;
  margin-left: -4px;
}
.detail__title {
  overflow-wrap: anywhere;
}
.detail__inline {
  display: flex;
  gap: 8px;
}
.detail__links-block {
  display: grid;
  gap: 4px;
  min-width: 0;
}
.detail__links-block h3 {
  margin: 0;
}
.detail__links {
  max-height: 200px;
  margin: 0;
  padding: 4px;
  overflow-y: auto;
  border: 1px solid var(--ll-outline-variant);
  border-radius: var(--ll-radius);
  background: var(--ll-surface);
  list-style: none;
}
.detail__link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 4px 8px;
}
.detail__link-text {
  display: grid;
  min-width: 0;
}
.detail__link-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}
.detail__link-site {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}
.detail__copy {
  min-height: 28px;
  flex: none;
}
</style>
