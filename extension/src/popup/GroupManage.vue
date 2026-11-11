<script setup lang="ts">
// One group, changed from "My lists": its name, who can open it, the lists in it and their
// order, and deleting it.
//
// What this account may do comes from the server (`canEdit`, `canSet`, `canAddList`,
// `canDelete`), and the server decides again on every request. A group never opens a list
// to anyone (invariant 5): adding a list here, or taking it out, leaves the list as it is.
// Taking a list out and deleting the group are asked about first, in place.
import { computed, nextTick, ref } from 'vue'

import { Disconnected } from '../lib/account'
import { errorMessage } from '../lib/api'
import { changeGroup, deleteGroup, moveInGroup, takeOutOfGroup } from '../lib/groups'
import { addToGroup, fetchGroupLists, type GroupSummary } from '../lib/lists'
import type { ListSummary, Visibility } from '../lib/storage'
import { VISIBILITIES, VISIBILITY, whoCanOpen } from '../lib/visibility'
import NoticeBox from '../ui/NoticeBox.vue'

const props = defineProps<{
  group: GroupSummary
  /** The lists the group shows this account, in the group's order. */
  lists: ListSummary[]
  /** The account's lists: the ones not in the group yet can be added. */
  mine: ListSummary[]
}>()
const emit = defineEmits<{
  done: []
  /** The group as the site has it now. */
  changed: [group: GroupSummary]
  /** The group's lists as the site has them now. */
  lists: [lists: ListSummary[]]
  deleted: []
  disconnected: []
}>()

const note = ref<{ tone: 'info' | 'success' | 'error'; text: string }>()
const busy = ref(false)
const root = ref<HTMLElement>()

function failed(error: unknown) {
  if (error instanceof Disconnected) emit('disconnected')
  else note.value = { tone: 'error', text: errorMessage(error) }
}

/** Runs one change: one at a time, and whatever goes wrong is said. True if it worked. */
async function change(work: () => Promise<void>): Promise<boolean> {
  busy.value = true
  note.value = undefined
  try {
    await work()
    return true
  } catch (error) {
    failed(error)
    return false
  } finally {
    busy.value = false
  }
}

/** Puts the keyboard where the user was, once the rows are drawn again. */
async function focusOn(selector: string) {
  await nextTick()
  const found = root.value?.querySelector<HTMLElement>(selector)
  ;(found ?? root.value?.querySelector<HTMLElement>('.manage__done'))?.focus()
}

/** The group's lists as the site has them, after a change the popup can't work out itself. */
async function reload() {
  const lists = await fetchGroupLists(props.group.code)
  emit('lists', lists)
  emit('changed', { ...props.group, listCount: lists.length })
}

// Its name.
const title = ref(props.group.title)
const renamed = computed(
  () => title.value.trim() !== '' && title.value.trim() !== props.group.title,
)
async function rename() {
  if (!renamed.value) return
  await change(async () => {
    const group = await changeGroup(props.group.code, { title: title.value.trim() })
    title.value = group.title
    emit('changed', group)
    note.value = { tone: 'success', text: `The group is now called “${group.title}”.` }
  })
}

// Who can open it: changed only by choosing another answer and then "Change".
const choice = ref<Visibility>(props.group.visibility)
async function changeVisibility() {
  if (choice.value === props.group.visibility) return
  const worked = await change(async () => {
    const group = await changeGroup(props.group.code, { visibility: choice.value })
    emit('changed', group)
    note.value = {
      tone: 'success',
      text: `Changed. ${whoCanOpen(group.visibility, 'group', group.canSet)} Its lists are as they were.`,
    }
  })
  if (!worked) choice.value = props.group.visibility // nothing changed
}

// A list of the account's that isn't in the group yet.
const addable = computed(() =>
  props.mine.filter((list) => !props.lists.some((other) => other.code === list.code)),
)
const adding = ref('')
async function add() {
  const list = addable.value.find((other) => other.code === adding.value)
  if (!list) return
  await change(async () => {
    const outcome = await addToGroup(props.group.code, list.code)
    if (!outcome.added) {
      note.value = { tone: 'info', text: outcome.reason }
      return
    }
    adding.value = ''
    await reload()
    note.value = { tone: 'success', text: `Added “${list.title}” to the group.` }
  })
}

// The order: by the arrows, or by dragging a row onto another.
async function moveTo(list: ListSummary, to: number): Promise<boolean> {
  const from = props.lists.findIndex((other) => other.code === list.code)
  if (from < 0 || to < 0 || to >= props.lists.length || to === from) return false
  const worked = await change(async () => {
    const lists = await moveInGroup(props.group.code, list.code, to)
    emit('lists', lists)
    const place = lists.findIndex((other) => other.code === list.code) + 1
    note.value = { tone: 'info', text: `“${list.title}” is now ${place} of ${lists.length}.` }
  })
  if (!worked) await reload().catch(() => {}) // the order here may not be the site's any more
  return worked
}

async function move(list: ListSummary, by: -1 | 1) {
  const from = props.lists.findIndex((other) => other.code === list.code)
  await moveTo(list, from + by)
  const row = `[data-list="${list.code}"]`
  const same = by < 0 ? '.manage__up' : '.manage__down'
  const other = by < 0 ? '.manage__down' : '.manage__up'
  await focusOn(`${row} ${same}:not(:disabled), ${row} ${other}:not(:disabled)`)
}

const dragged = ref('')
const over = ref('')

function dragStart(event: DragEvent, list: ListSummary) {
  if (busy.value || !event.dataTransfer) return event.preventDefault()
  dragged.value = list.code
  event.dataTransfer.effectAllowed = 'move'
  // Firefox starts no drag without data. The title only: nothing to drop elsewhere.
  event.dataTransfer.setData('text/plain', list.title)
}

function dragOver(event: DragEvent, list: ListSummary) {
  if (!dragged.value) return // something else is being dragged over the popup
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
  over.value = list.code
}

function dragEnd() {
  dragged.value = ''
  over.value = ''
}

async function drop(event: DragEvent, onto: ListSummary) {
  const list = props.lists.find((other) => other.code === dragged.value)
  dragEnd()
  if (!list) return
  event.preventDefault()
  const to = props.lists.findIndex((other) => other.code === onto.code)
  if (await moveTo(list, to))
    await focusOn(`[data-list="${list.code}"] .manage__move:not(:disabled)`)
}

// Taking a list out: asked about in its row.
const asking = ref('')
async function ask(list: ListSummary) {
  asking.value = list.code
  await focusOn(`[data-list="${list.code}"] .manage__keep`)
}
async function keep(list: ListSummary) {
  asking.value = ''
  await focusOn(`[data-list="${list.code}"] .manage__out`)
}
async function takeOut(list: ListSummary) {
  const worked = await change(async () => {
    await takeOutOfGroup(props.group.code, list.code)
    const lists = props.lists.filter((other) => other.code !== list.code)
    emit('lists', lists)
    emit('changed', { ...props.group, listCount: lists.length })
    note.value = {
      tone: 'success',
      text: `“${list.title}” is no longer in the group. The list itself is as it was.`,
    }
  })
  asking.value = ''
  if (!worked) await reload().catch(() => {})
  await focusOn('.manage__done')
}

// Deleting the group: asked about first.
const deleting = ref(false)
async function askDelete() {
  deleting.value = true
  await focusOn('.manage__keep-group')
}
async function keepGroup() {
  deleting.value = false
  await focusOn('.manage__delete')
}
async function remove() {
  const worked = await change(async () => {
    await deleteGroup(props.group.code)
  })
  deleting.value = false
  if (worked) emit('deleted')
}
</script>

<template>
  <section ref="root" class="manage" aria-labelledby="manage-title">
    <div class="manage__head">
      <h2 id="manage-title" class="manage__title">Group: {{ group.title }}</h2>
      <button type="button" class="ll-button ll-button--text manage__done" @click="emit('done')">
        Done
      </button>
    </div>
    <NoticeBox v-if="note" :tone="note.tone">{{ note.text }}</NoticeBox>

    <div v-if="group.canEdit" class="ll-field">
      <label for="manage-name">Name</label>
      <div class="manage__inline">
        <input
          id="manage-name"
          v-model="title"
          class="ll-input"
          maxlength="255"
          autocomplete="off"
          :disabled="busy"
          @keydown.enter.prevent="rename"
        />
        <button
          type="button"
          class="ll-button ll-button--tonal"
          :disabled="busy || !renamed"
          @click="rename"
        >
          Rename
        </button>
      </div>
    </div>

    <div v-if="group.canSet" class="ll-field">
      <label for="manage-visibility">Who can open it</label>
      <div class="manage__inline">
        <select id="manage-visibility" v-model="choice" class="ll-input" :disabled="busy">
          <option v-for="value in VISIBILITIES" :key="value" :value="value">
            {{ VISIBILITY[value] }}
          </option>
        </select>
        <button
          type="button"
          class="ll-button ll-button--tonal"
          :disabled="busy || choice === group.visibility"
          @click="changeVisibility"
        >
          Change
        </button>
      </div>
      <p class="ll-muted manage__hint">
        A group shows each person only the lists they can open themselves.
      </p>
    </div>

    <div v-if="group.canAddList && addable.length" class="ll-field">
      <label for="manage-add">Add a list</label>
      <div class="manage__inline">
        <select id="manage-add" v-model="adding" class="ll-input" :disabled="busy">
          <option value="" disabled>Choose a list</option>
          <option v-for="list in addable" :key="list.code" :value="list.code">
            {{ list.title }}
          </option>
        </select>
        <button
          type="button"
          class="ll-button ll-button--tonal"
          :disabled="busy || !adding"
          @click="add"
        >
          Add
        </button>
      </div>
    </div>

    <div class="manage__block">
      <h3 class="ll-label">Lists in this group</h3>
      <p v-if="!lists.length" class="ll-muted">This group shows you no lists.</p>
      <template v-else>
        <p v-if="group.canEdit && lists.length > 1" class="ll-muted manage__hint">
          Drag a list to another place, or use the arrows.
        </p>
        <ul class="manage__lists">
          <li
            v-for="(list, index) in lists"
            :key="list.code"
            class="manage__list"
            :class="{
              'manage__list--movable': group.canEdit,
              'manage__list--dragged': dragged === list.code,
              'manage__list--over': over === list.code && dragged !== list.code,
            }"
            :data-list="list.code"
            :draggable="group.canEdit ? 'true' : undefined"
            @dragstart="dragStart($event, list)"
            @dragover="dragOver($event, list)"
            @drop="drop($event, list)"
            @dragend="dragEnd"
          >
            <span v-if="group.canEdit" class="manage__moves">
              <button
                type="button"
                class="ll-button ll-button--text manage__move manage__up"
                :disabled="busy || index === 0"
                :aria-label="`Move ${list.title} up`"
                title="Move up"
                @click="move(list, -1)"
              >
                <span aria-hidden="true">↑</span>
              </button>
              <button
                type="button"
                class="ll-button ll-button--text manage__move manage__down"
                :disabled="busy || index === lists.length - 1"
                :aria-label="`Move ${list.title} down`"
                title="Move down"
                @click="move(list, 1)"
              >
                <span aria-hidden="true">↓</span>
              </button>
            </span>
            <span class="manage__name">{{ list.title }}</span>
            <template v-if="group.canEdit">
              <span v-if="asking === list.code" class="manage__asking">
                <button
                  type="button"
                  class="ll-button ll-button--danger manage__small"
                  :disabled="busy"
                  :aria-label="`Take ${list.title} out of the group`"
                  @click="takeOut(list)"
                >
                  Take out
                </button>
                <button
                  type="button"
                  class="ll-button ll-button--text manage__small manage__keep"
                  :disabled="busy"
                  @click="keep(list)"
                >
                  Keep
                </button>
              </span>
              <button
                v-else
                type="button"
                class="ll-button ll-button--text manage__small manage__out"
                :disabled="busy"
                :aria-label="`Take ${list.title} out…`"
                @click="ask(list)"
              >
                Take out…
              </button>
            </template>
          </li>
        </ul>
      </template>
    </div>

    <div v-if="group.canDelete" class="manage__danger">
      <template v-if="deleting">
        <p>Delete this group? Its lists stay as they are; only the group goes.</p>
        <div class="ll-row">
          <button
            type="button"
            class="ll-button ll-button--danger"
            :disabled="busy"
            @click="remove"
          >
            Delete group
          </button>
          <button
            type="button"
            class="ll-button ll-button--text manage__keep-group"
            :disabled="busy"
            @click="keepGroup"
          >
            Keep
          </button>
        </div>
      </template>
      <button
        v-else
        type="button"
        class="ll-button ll-button--text manage__delete"
        :disabled="busy"
        @click="askDelete"
      >
        Delete group…
      </button>
    </div>
  </section>
</template>

<style scoped>
.manage {
  display: grid;
  gap: 12px;
  min-width: 0;
}
.manage__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.manage__title {
  overflow-wrap: anywhere;
}
.manage__done {
  flex: none;
  min-height: 28px;
}
.manage__inline {
  display: flex;
  gap: 8px;
}
.manage__hint {
  font-size: 12px;
}
.manage__block {
  display: grid;
  gap: 4px;
  min-width: 0;
}
.manage__block h3 {
  margin: 0;
}
.manage__lists {
  max-height: 200px;
  margin: 0;
  padding: 4px;
  overflow-y: auto;
  border: 1px solid var(--ll-outline-variant);
  border-radius: var(--ll-radius);
  background: var(--ll-surface);
  list-style: none;
}
.manage__list {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: var(--ll-radius);
}
.manage__list--movable {
  cursor: grab;
}
.manage__list--dragged {
  opacity: 0.45;
}
.manage__list--over {
  outline: 2px solid var(--ll-primary);
  outline-offset: -2px;
}
.manage__moves,
.manage__asking {
  display: flex;
  flex: none;
  gap: 2px;
}
.manage__move {
  min-width: 28px;
  min-height: 28px;
  padding: 0;
}
.manage__name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}
.manage__small {
  flex: none;
  min-height: 28px;
}
.manage__danger {
  display: grid;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--ll-outline-variant);
}
</style>
