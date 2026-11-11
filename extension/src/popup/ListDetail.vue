<script setup lang="ts">
// One list, looked into from "My lists": its links, its address to copy or open, who can open
// it (and changing that, for its owner), adding it to a group, and, for who may edit it,
// putting its links in another order or removing them ("Edit links").
//
// Copying a link never changes who can open the list: that only happens when the user picks
// another answer under "Who can open it" and chooses Change (invariant 2). What this account
// may do comes from the server (`canSet`, `canAddList`), and the server decides again on
// every request.
import { computed, nextTick, onMounted, ref } from 'vue'

import { Disconnected } from '../lib/account'
import { errorMessage } from '../lib/api'
import { copyText } from '../lib/clipboard'
import {
  addToGroup,
  fetchLinks,
  type GroupSummary,
  type LinkSummary,
  moveLink,
  removeLink,
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

async function loadLinks() {
  try {
    links.value = await fetchLinks(props.list.code)
    linksError.value = ''
  } catch (error) {
    if (error instanceof Disconnected) emit('disconnected')
    else linksError.value = errorMessage(error)
  }
}
onMounted(loadLinks)

// Editing the links: another order, or one fewer. Each is one change in the list's history,
// made by the site; a removal is asked about first, in the row itself.
const editing = ref(false)
/** The link whose removal is being asked about. */
const asking = ref('')
const block = ref<HTMLElement>()

function edit(on: boolean) {
  editing.value = on
  asking.value = ''
}

/** Puts the keyboard where the user was, once the rows are drawn again. */
async function focusOn(selector: string) {
  await nextTick()
  const found = block.value?.querySelector<HTMLElement>(selector)
  ;(found ?? block.value?.querySelector<HTMLElement>('.detail__edit'))?.focus()
}

/** Puts `link` at place `to` (0-based). True if the site did. */
async function moveTo(link: LinkSummary, to: number): Promise<boolean> {
  const from = links.value?.findIndex((other) => other.id === link.id) ?? -1
  if (!links.value || from < 0 || to < 0 || to >= links.value.length || to === from) return false
  busy.value = true
  note.value = undefined
  try {
    links.value = await moveLink(props.list.code, link.id, to)
    const place = links.value.findIndex((other) => other.id === link.id) + 1
    note.value = {
      tone: 'info',
      text: `“${link.title}” is now ${place} of ${links.value.length}.`,
    }
    return true
  } catch (error) {
    failed(error)
    await loadLinks() // the order here may not be the site's any more
    return false
  } finally {
    busy.value = false
  }
}

async function move(link: LinkSummary, by: -1 | 1) {
  const from = links.value?.findIndex((other) => other.id === link.id) ?? -1
  await moveTo(link, from + by)
  // The same button, or the other one where the link reached an end.
  const row = `[data-link="${link.id}"]`
  const same = by < 0 ? '.detail__up' : '.detail__down'
  const other = by < 0 ? '.detail__down' : '.detail__up'
  await focusOn(`${row} ${same}:not(:disabled), ${row} ${other}:not(:disabled)`)
}

// Dragging a row onto another puts it in that one's place: the same move as the arrows, which
// stay for the keyboard. Only while editing, and never from the row's buttons or its link.
const dragged = ref('')
const over = ref('')

function dragStart(event: DragEvent, link: LinkSummary) {
  if (busy.value || !event.dataTransfer) return event.preventDefault()
  dragged.value = link.id
  event.dataTransfer.effectAllowed = 'move'
  // Firefox starts no drag without data. The title only: nothing to drop elsewhere.
  event.dataTransfer.setData('text/plain', link.title)
}

function dragOver(event: DragEvent, link: LinkSummary) {
  if (!dragged.value) return // something else is being dragged over the popup
  event.preventDefault() // "this is a place to drop"
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
  over.value = link.id
}

function dragEnd() {
  dragged.value = ''
  over.value = ''
}

async function drop(event: DragEvent, onto: LinkSummary) {
  const link = links.value?.find((other) => other.id === dragged.value)
  dragEnd()
  if (!link) return
  event.preventDefault()
  const to = links.value?.findIndex((other) => other.id === onto.id) ?? -1
  if (await moveTo(link, to)) await focusOn(`[data-link="${link.id}"] .detail__move:not(:disabled)`)
}

async function ask(link: LinkSummary) {
  asking.value = link.id
  await focusOn(`[data-link="${link.id}"] .detail__keep`)
}

async function keep(link: LinkSummary) {
  asking.value = ''
  await focusOn(`[data-link="${link.id}"] .detail__remove`)
}

async function remove(link: LinkSummary) {
  busy.value = true
  note.value = undefined
  try {
    const list = await removeLink(props.list, link.id)
    links.value = links.value?.filter((other) => other.id !== link.id)
    emit('changed', list)
    note.value = {
      tone: 'success',
      text: `Removed “${link.title}”. The list's history on listlinkedin still has it.`,
    }
  } catch (error) {
    failed(error)
    await loadLinks()
  } finally {
    busy.value = false
    asking.value = ''
  }
  await focusOn('.detail__edit')
}

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

    <div ref="block" class="detail__links-block">
      <div class="detail__links-head">
        <h3 class="ll-label">Links</h3>
        <button
          v-if="list.canEdit && links?.length"
          type="button"
          class="ll-button ll-button--text detail__edit"
          :aria-pressed="editing"
          @click="edit(!editing)"
        >
          {{ editing ? 'Done' : 'Edit links' }}
        </button>
      </div>
      <p v-if="editing && links?.length" class="ll-muted detail__hint">
        Drag a link to another place, or use the arrows.
      </p>
      <NoticeBox v-if="linksError" tone="error">{{ linksError }}</NoticeBox>
      <p v-else-if="!links" class="ll-muted" aria-busy="true">Loading the links…</p>
      <p v-else-if="!links.length" class="ll-muted">This list has no links yet.</p>
      <ul v-else class="detail__links">
        <li
          v-for="(link, index) in links"
          :key="link.id"
          class="detail__link"
          :class="{
            'detail__link--movable': editing && list.canEdit,
            'detail__link--dragged': dragged === link.id,
            'detail__link--over': over === link.id && dragged !== link.id,
          }"
          :data-link="link.id"
          :draggable="editing && list.canEdit ? 'true' : undefined"
          @dragstart="dragStart($event, link)"
          @dragover="dragOver($event, link)"
          @drop="drop($event, link)"
          @dragend="dragEnd"
        >
          <span v-if="editing && list.canEdit" class="detail__moves">
            <button
              type="button"
              class="ll-button ll-button--text detail__move detail__up"
              :disabled="busy || index === 0"
              :aria-label="`Move ${link.title} up`"
              title="Move up"
              @click="move(link, -1)"
            >
              <span aria-hidden="true">↑</span>
            </button>
            <button
              type="button"
              class="ll-button ll-button--text detail__move detail__down"
              :disabled="busy || index === links.length - 1"
              :aria-label="`Move ${link.title} down`"
              title="Move down"
              @click="move(link, 1)"
            >
              <span aria-hidden="true">↓</span>
            </button>
          </span>
          <span class="detail__link-text">
            <a
              v-if="isWeb(link.url)"
              class="detail__link-title"
              :href="link.url"
              target="_blank"
              rel="noreferrer"
              :draggable="editing ? 'false' : undefined"
            >
              {{ link.title }}
            </a>
            <span v-else class="detail__link-title">{{ link.title }}</span>
            <span class="detail__link-site ll-muted">{{ link.site }}</span>
          </span>
          <template v-if="editing && list.canEdit">
            <span v-if="asking === link.id" class="detail__asking">
              <button
                type="button"
                class="ll-button ll-button--danger detail__copy"
                :disabled="busy"
                :aria-label="`Remove ${link.title} from the list`"
                @click="remove(link)"
              >
                Remove
              </button>
              <button
                type="button"
                class="ll-button ll-button--text detail__copy detail__keep"
                :disabled="busy"
                @click="keep(link)"
              >
                Keep
              </button>
            </span>
            <button
              v-else
              type="button"
              class="ll-button ll-button--text detail__copy detail__remove"
              :disabled="busy"
              :aria-label="`Remove ${link.title}…`"
              @click="ask(link)"
            >
              Remove…
            </button>
          </template>
          <button
            v-else-if="link.shortUrl"
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
.detail__links-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 28px;
}
.detail__hint {
  font-size: 12px;
}
.detail__edit {
  min-height: 28px;
  padding: 0 4px;
}
.detail__moves,
.detail__asking {
  display: flex;
  flex: none;
  gap: 2px;
}
.detail__move {
  min-width: 28px;
  min-height: 28px;
  padding: 0;
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
.detail__link--movable {
  border-radius: var(--ll-radius);
  cursor: grab;
}
.detail__link--dragged {
  opacity: 0.45;
}
.detail__link--over {
  outline: 2px solid var(--ll-primary);
  outline-offset: -2px;
}
.detail__link-text {
  display: grid;
  flex: 1;
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
