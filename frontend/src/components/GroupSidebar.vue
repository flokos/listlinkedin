<script setup lang="ts">
// The lists of a group (docs/v2/11-UI-UX-MIGRATION.md#groups-workspace): a permanent drawer
// on wide screens, a rail that expands on keyboard focus or its toggle in between, and a modal
// drawer on phones and tablets (Escape closes it, focus returns to the button that opened
// it). Only the lists this viewer may see are here; the server leaves the others out.
//
// In reorder mode, lists can be dragged by their handle or moved with the Move buttons
// (the non-dragging way, WCAG 2.2 SC 2.5.7), and taken out of the group.
import {
  mdiArrowCollapseLeft,
  mdiArrowDown,
  mdiArrowExpandRight,
  mdiArrowUp,
  mdiClose,
  mdiDragVertical,
  mdiEyeOffOutline,
} from '@mdi/js'
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { VueDraggable, type DraggableEvent } from 'vue-draggable-plus'

import type { GroupList } from '../api'
import { initialsOf } from '../utils/initials'

export type SidebarMode = 'permanent' | 'rail' | 'temporary'

const open = defineModel<boolean>({ required: true })
const reordering = defineModel<boolean>('reordering', { required: true })
const props = defineProps<{
  mode: SidebarMode
  groupTitle: string
  groupCode: string
  lists: GroupList[]
  /** The list shown now. */
  currentCode: string | undefined
  canEdit: boolean
  /** A move is being saved: the controls wait for it. */
  busy: boolean
}>()
const emit = defineEmits<{
  move: [GroupList, number]
  remove: [GroupList]
}>()

const expanded = ref(false)
// The drawer renders a fragment (with its scrim), so its own $el isn't an element: use the nav.
const nav = ref<HTMLElement>()

// The rail opens while keyboard focus is inside it, so keyboard users can read the names, and
// stays open while reordering. Pointer focus doesn't count: a click on the toggle must not
// first open the rail and then close it again.
function onFocusIn(event: FocusEvent) {
  const target = event.target as HTMLElement | null
  if (props.mode === 'rail' && target?.matches(':focus-visible')) expanded.value = true
}
function onFocusOut(event: FocusEvent) {
  const next = event.relatedTarget as Node | null
  if (props.mode === 'rail' && !reordering.value && !nav.value?.contains(next))
    expanded.value = false
}
// On phones, reordering opens the drawer, and Done closes it again.
watch(reordering, (value) => {
  if (props.mode === 'rail') expanded.value = value
  if (props.mode === 'temporary') open.value = value
})
watch(open, (value) => {
  if (!value && props.mode === 'temporary') reordering.value = false
})

// Modal drawer: Escape closes it and focus goes back to the button that opened it. Choosing a
// list navigates; the page then moves focus to the list's heading.
let opener: HTMLElement | null = null
function onKeydown(event: KeyboardEvent) {
  if (event.key !== 'Escape' || props.mode !== 'temporary') return
  if (document.querySelector('.v-overlay--active.v-dialog')) return // a dialog's own Escape
  open.value = false
  opener?.focus()
}
watch(
  () => props.mode === 'temporary' && open.value,
  async (modal) => {
    if (modal) {
      opener = document.activeElement as HTMLElement | null
      window.addEventListener('keydown', onKeydown)
      await nextTick()
      // After the slide-in starts; focusing a hidden element does nothing.
      setTimeout(() => {
        const target =
          nav.value?.querySelector<HTMLElement>('[aria-current="page"]') ??
          nav.value?.querySelector<HTMLElement>('a[href], button')
        target?.focus()
      }, 150)
    } else {
      window.removeEventListener('keydown', onKeydown)
    }
  },
)
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))

function closeIfModal() {
  if (props.mode === 'temporary') open.value = false
}

// Reordering: the draggable works on its own copy so a drop shows at once; the page's answer
// replaces it.
const items = ref<GroupList[]>([...props.lists])
watch(
  () => props.lists,
  (lists) => (items.value = [...lists]),
)
function onEnd(event: DraggableEvent) {
  const { oldIndex, newIndex } = event
  if (oldIndex === undefined || newIndex === undefined || oldIndex === newIndex) return
  emit('move', props.lists[oldIndex]!, newIndex)
}

const label = computed(() => `Lists in ${props.groupTitle}`)
const listRoute = (item: GroupList) => ({
  name: 'group-list',
  params: { code: props.groupCode, listCode: item.code },
})
</script>

<template>
  <v-navigation-drawer
    v-model="open"
    v-model:expanded="expanded"
    class="ll-group-sidebar"
    :permanent="mode !== 'temporary'"
    :temporary="mode === 'temporary'"
    :rail="mode === 'rail'"
    :width="280"
    :rail-width="64"
    :role="mode === 'temporary' && open ? 'dialog' : undefined"
    :aria-modal="mode === 'temporary' && open ? 'true' : undefined"
    :aria-label="mode === 'temporary' ? label : undefined"
    @focusin="onFocusIn"
    @focusout="onFocusOut"
  >
    <nav ref="nav" :aria-label="label">
      <div class="d-flex align-center ga-1 px-3 pt-3 pb-1 ll-group-sidebar__head">
        <p class="text-title-small text-medium-emphasis ll-group-sidebar__title flex-grow-1">
          {{ reordering ? 'Reorder lists' : 'Lists' }}
        </p>
        <v-btn
          v-if="mode === 'rail' && !reordering"
          :icon="expanded ? mdiArrowCollapseLeft : mdiArrowExpandRight"
          variant="text"
          size="small"
          :aria-label="expanded ? 'Hide list names' : 'Show list names'"
          :aria-expanded="expanded ? 'true' : 'false'"
          @click="expanded = !expanded"
        />
        <v-btn
          v-if="mode === 'temporary' && !reordering"
          :icon="mdiClose"
          variant="text"
          size="small"
          aria-label="Close lists"
          @click="open = false"
        />
        <v-btn
          v-if="reordering"
          color="primary"
          variant="tonal"
          size="small"
          @click="reordering = false"
          >Done</v-btn
        >
      </div>

      <p v-if="!lists.length" class="px-4 py-2 text-body-small text-medium-emphasis">
        No lists yet.
      </p>

      <!-- Browsing: one link per list. Vuetify would make this a "list" of links, which
           isn't valid ARIA; the <nav> is what groups them. -->
      <v-list v-else-if="!reordering" nav density="comfortable" class="pt-1" role="none">
        <v-list-item
          v-for="item in lists"
          :key="item.code"
          :to="listRoute(item)"
          :active="item.code === currentCode"
          :aria-current="item.code === currentCode ? 'page' : undefined"
          color="primary"
          rounded="lg"
          @click="closeIfModal"
        >
          <template #prepend>
            <v-avatar size="32" rounded="lg" color="primary-container" class="text-label-medium">
              <v-img v-if="item.image_url" :src="item.image_url" alt="" cover />
              <span v-else aria-hidden="true">{{ initialsOf(item.title) }}</span>
            </v-avatar>
          </template>
          <v-list-item-title class="ll-group-sidebar__name">{{ item.title }}</v-list-item-title>
          <template v-if="!item.shown_to_all" #append>
            <v-icon
              :icon="mdiEyeOffOutline"
              size="16"
              class="text-medium-emphasis"
              aria-hidden="true"
            />
            <span class="ll-sr-only">(not everyone in the group sees this list)</span>
          </template>
        </v-list-item>
      </v-list>

      <!-- Reordering: drag by the handle, or use the buttons. -->
      <VueDraggable
        v-else
        v-model="items"
        tag="ol"
        class="ll-group-sidebar__order pa-2"
        handle=".ll-drag-handle"
        :disabled="busy"
        :animation="150"
        :force-fallback="true"
        :delay="250"
        :delay-on-touch-only="true"
        :fallback-tolerance="4"
        ghost-class="ll-drag-ghost"
        aria-label="Order of the lists"
        @end="onEnd"
      >
        <li v-for="(item, index) in items" :key="item.code" class="ll-group-sidebar__row">
          <v-icon
            :icon="mdiDragVertical"
            class="ll-drag-handle text-medium-emphasis"
            aria-hidden="true"
          />
          <span class="ll-group-sidebar__name text-body-medium flex-grow-1">{{ item.title }}</span>
          <v-btn
            :icon="mdiArrowUp"
            variant="text"
            size="x-small"
            :disabled="busy || index === 0"
            :aria-label="`Move ${item.title} up`"
            @click="emit('move', item, index - 1)"
          />
          <v-btn
            :icon="mdiArrowDown"
            variant="text"
            size="x-small"
            :disabled="busy || index === items.length - 1"
            :aria-label="`Move ${item.title} down`"
            @click="emit('move', item, index + 1)"
          />
          <v-btn
            :icon="mdiClose"
            variant="text"
            size="x-small"
            :disabled="busy"
            :aria-label="`Remove ${item.title} from the group`"
            @click="emit('remove', item)"
          />
        </li>
      </VueDraggable>
      <p
        v-if="lists.some((l) => !l.shown_to_all) && (mode !== 'rail' || expanded)"
        class="px-4 py-3 text-body-small text-medium-emphasis"
      >
        <v-icon :icon="mdiEyeOffOutline" size="16" aria-hidden="true" />
        Only people who may open these lists see them here.
      </p>
    </nav>
  </v-navigation-drawer>
</template>

<style scoped>
.ll-group-sidebar__title,
.ll-group-sidebar__name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin: 0;
}
.ll-group-sidebar__order {
  list-style: none;
  display: grid;
  gap: 4px;
}
.ll-group-sidebar__row {
  display: flex;
  align-items: center;
  gap: 2px;
  min-width: 0;
  padding: 4px 4px 4px 0;
  border-radius: 12px;
  background: rgb(var(--v-theme-surface-container));
}
.ll-drag-handle {
  cursor: grab;
  touch-action: none;
}
:deep(.ll-drag-ghost) {
  opacity: 0.4;
}
.v-navigation-drawer--rail:not(.v-navigation-drawer--expanded) .ll-group-sidebar__title {
  visibility: hidden;
}
</style>
