<script setup lang="ts">
import {
  mdiAlertCircleOutline,
  mdiArrowLeft,
  mdiCalendarRemoveOutline,
  mdiLinkOff,
  mdiLinkVariantPlus,
  mdiMagnify,
  mdiPlus,
  mdiRefresh,
} from '@mdi/js'
import { computed, ref, toRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  errorMessage,
  reportList,
  type ReportInput,
  type LinkInput,
  type ListDetail,
  type SharedLink,
  type Visibility,
} from '../api'
import AddLinkCard from '../components/AddLinkCard.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import CopyListDialog from '../components/CopyListDialog.vue'
import LinkCollection from '../components/LinkCollection.vue'
import LinkDetailsDialog from '../components/LinkDetailsDialog.vue'
import LinkEditDialog from '../components/LinkEditDialog.vue'
import ListHeader from '../components/ListHeader.vue'
import ListPickerDialog from '../components/ListPickerDialog.vue'
import LiveRegion from '../components/LiveRegion.vue'
import MovePositionDialog from '../components/MovePositionDialog.vue'
import ReportDialog from '../components/ReportDialog.vue'
import ListToolbar, { type LinkSort } from '../components/ListToolbar.vue'
import ShareDialog from '../components/ShareDialog.vue'
import StatePanel from '../components/StatePanel.vue'
import { useListPage } from '../composables/useListPage'
import { useNotify } from '../composables/useNotify'
import { useQueryDialog } from '../composables/useQueryDialog'
import { useSession } from '../composables/useSession'
import { useViewPreference } from '../composables/useViewPreference'

const props = defineProps<{
  code: string
  /** Shown inside a group's workspace (/g/{code}/l/{listCode}): the group's page keeps the
   * navigation, and a deleted or left list goes back to the group instead of My lists. */
  inGroup?: { title: string }
}>()
const emit = defineEmits<{
  /** The list as loaded or last changed, e.g. renamed (for the group's sidebar). */
  loaded: [ListDetail]
  /** The list was deleted, or the viewer left it. */
  gone: []
}>()
const route = useRoute()
const router = useRouter()
const notify = useNotify()
const page = useListPage(toRef(props, 'code'))
const { list, links, status, isOwner } = page
const session = useSession()
const { view } = useViewPreference()

// Title follows the list's name.
watch([list, status], ([value, state]) => {
  const titles: Partial<Record<typeof state, string>> = {
    'not-found': 'List not found',
    expired: 'List expired',
    error: "Couldn't load list",
  }
  const title = titles[state] ?? (state === 'ready' ? value?.title : undefined)
  const group = props.inGroup ? ` · ${props.inGroup.title}` : ''
  if (title) document.title = `${title}${group} · listlinkedin`
  if (state === 'ready' && value) emit('loaded', value)
})

// Back link: to My lists when the user came from there.
const cameFromMyLists = computed(
  () => !props.inGroup && String(window.history.state?.back ?? '').startsWith('/lists'),
)

// Search and sort (client-side: a list holds at most 100 links, all loaded at once). The
// server sends the stored order; "Newest" and "A–Z" are only views of it.
const search = ref('')
const sort = ref<LinkSort>('custom')
const shownTitle = (l: SharedLink) => l.display?.title ?? l.title ?? l.destination_url
const visibleLinks = computed(() => {
  const q = search.value.trim().toLowerCase()
  const matches = q
    ? links.value.filter((l) =>
        [shownTitle(l), l.destination_url, l.display?.description ?? l.description ?? ''].some(
          (text) => text.toLowerCase().includes(q),
        ),
      )
    : links.value
  if (sort.value === 'custom') return matches
  if (sort.value === 'newest') {
    return [...matches].sort(
      (a, b) => b.created_at.localeCompare(a.created_at) || b.id.localeCompare(a.id),
    )
  }
  const key = (l: SharedLink) =>
    (
      l.title ||
      l.display?.title ||
      l.destination_url.replace(/^https?:\/\/(www\.)?/, '')
    ).toLowerCase()
  return [...matches].sort((a, b) => key(a).localeCompare(key(b)))
})

// Moving links: by dragging or the ⋮ Move items, only while the stored order is shown.
const reorderable = computed(() => sort.value === 'custom' && !search.value.trim())
const canMoveToList = computed(() => isOwner.value && session.isSignedIn.value)
const announcement = ref<{ text: string } | null>(null)

async function moveLink(link: SharedLink, index: number) {
  try {
    await page.moveLink(link.id, index)
    const at = links.value.findIndex((l) => l.id === link.id) + 1
    announcement.value = {
      text: `${shownTitle(link)} moved to position ${at} of ${links.value.length}.`,
    }
  } catch (error) {
    notify.error(errorMessage(error))
  }
}
const positionId = ref<string | null>(null)
const positionOpen = computed({
  get: () => positionId.value !== null,
  set: (v) => !v && (positionId.value = null),
})
const positionLink = computed(() => byId(positionId.value))
const pickerId = ref<string | null>(null)
const pickerOpen = computed({
  get: () => pickerId.value !== null,
  set: (v) => !v && (pickerId.value = null),
})
const pickerLink = computed(() => byId(pickerId.value))
async function moveToList(target: ListDetail) {
  const link = pickerLink.value
  if (!link) return
  await page.moveToList(link.id, target.code)
  notify.success(`Moved to “${target.title}”`)
  announcement.value = { text: `${shownTitle(link)} moved to ${target.title}.` }
}

// Share dialog is reflected in the URL (?dialog=share) so the browser's Back button closes it.
const shareOpen = useQueryDialog('share')

// "Make a copy", also reflected in the URL (?dialog=copy): signing in first comes back to it.
const copyOpen = useQueryDialog('copy', () => page.can('fork'))
const signInToCopy = computed(() => !session.isSignedIn.value && Boolean(list.value?.allow_fork))
function startCopy() {
  if (session.isSignedIn.value) {
    copyOpen.value = true
    return
  }
  const next = router.resolve({ query: { ...route.query, dialog: 'copy' } }).fullPath
  router.push({ name: 'signin', query: { next } })
}
function openCopy(copy: ListDetail) {
  notify.success('Copy made. Only you can see it until you share it.')
  // Replaces the dialog's history entry, so Back returns to the original list.
  router.replace({ name: 'list', params: { code: copy.code, slug: copy.slug } })
}

async function rename(title: string) {
  await page.rename(title)
  notify.success('List renamed')
  return true
}

// Link details, editing and deletion. Dialogs follow the link by id, so they show its latest
// state (for example a new icon) while open.
const byId = (id: string | null) => links.value.find((l) => l.id === id) ?? null
const detailsId = ref<string | null>(null)
const detailsOpen = computed({
  get: () => detailsId.value !== null,
  set: (v) => !v && (detailsId.value = null),
})
const editingId = ref<string | null>(null)
const editOpen = computed({
  get: () => editingId.value !== null,
  set: (v) => !v && (editingId.value = null),
})
const deleting = ref<SharedLink | null>(null)
const deleteOpen = computed({
  get: () => deleting.value !== null,
  set: (v) => !v && (deleting.value = null),
})

async function addLink(input: LinkInput) {
  await page.addLink(input)
  notify.success('Link added')
}
async function saveLink(input: LinkInput) {
  if (!editingId.value) return
  await page.editLink(editingId.value, input)
  notify.success('Link updated')
}
async function setIcon(file: File | null) {
  if (!editingId.value) return
  await page.setLinkIcon(editingId.value, file)
  notify.success(file ? 'Icon updated' : 'Icon removed')
}
async function confirmDeleteLink() {
  if (!deleting.value) return
  try {
    await page.removeLink(deleting.value.id)
    notify.success('Link deleted')
  } catch (error) {
    notify.error(errorMessage(error))
    throw error
  }
}

// Owner actions in the menu.
const deleteListOpen = ref(false)

async function confirmDeleteList() {
  try {
    await page.removeList()
    notify.success('List deleted')
    if (props.inGroup) emit('gone')
    else router.replace({ name: 'saved-lists' })
  } catch (error) {
    notify.error(errorMessage(error))
    throw error
  }
}
async function setAllowFork(allow: boolean) {
  try {
    await page.change({ allow_fork: allow })
    notify.success(allow ? 'Copies allowed' : 'Copies turned off')
  } catch (error) {
    notify.error(errorMessage(error))
  }
}

async function setVisibility(visibility: Visibility) {
  try {
    await page.change({ visibility })
    notify.success('Sharing updated')
  } catch (error) {
    notify.error(errorMessage(error))
  }
}

// Anyone who can see the list, except its owner, may report it to the operator (task 9.0).
const reportOpen = ref(false)
const sendReport = (input: ReportInput) => reportList(props.code, input)

// Members may leave a list they were added to.
const leaveOpen = ref(false)
async function confirmLeave() {
  try {
    const title = list.value?.title
    await page.leave()
    notify.success(`You left “${title}”`)
    if (props.inGroup) emit('gone')
    else router.replace({ name: 'saved-lists' })
  } catch (error) {
    notify.error(errorMessage(error))
    throw error
  }
}
</script>

<template>
  <div :class="inGroup ? 'py-2 py-md-4' : 'll-content py-6 py-md-10'">
    <v-btn
      v-if="cameFromMyLists"
      :prepend-icon="mdiArrowLeft"
      variant="text"
      class="mb-4 ml-n3"
      @click="router.back()"
    >
      My lists
    </v-btn>

    <!-- Loading -->
    <div v-if="status === 'loading'" aria-busy="true" aria-label="Loading list">
      <v-skeleton-loader type="heading" class="mb-4" max-width="480" />
      <v-skeleton-loader type="chip, chip" class="mb-8" />
      <v-skeleton-loader v-for="n in 4" :key="n" type="list-item-avatar-two-line" class="mb-2" />
    </div>

    <!-- Unavailable -->
    <StatePanel
      v-else-if="status === 'not-found'"
      as="h1"
      :icon="mdiLinkOff"
      title="This list doesn't exist"
      :text="
        session.isSignedIn.value
          ? 'It may have been deleted, the link is mistyped, or it isn\'t shared with you.'
          : 'It may have been deleted, or the link is mistyped. If someone shared it with you, sign in to open it.'
      "
    >
      <template #actions>
        <v-btn
          v-if="!session.isSignedIn.value"
          color="primary"
          :to="{ name: 'signin', query: { next: route.fullPath } }"
        >
          Sign in
        </v-btn>
        <v-btn
          :color="session.isSignedIn.value ? 'primary' : undefined"
          :variant="session.isSignedIn.value ? 'flat' : 'text'"
          :to="{ name: 'home', hash: '#create' }"
        >
          Create a new list
        </v-btn>
      </template>
    </StatePanel>
    <StatePanel
      v-else-if="status === 'expired'"
      as="h1"
      tone="warning"
      :icon="mdiCalendarRemoveOutline"
      title="This list has expired"
      text="This list reached the end date it was given, and its short links no longer work."
    >
      <template #actions>
        <v-btn color="primary" :to="{ name: 'home', hash: '#create' }">Create a new list</v-btn>
      </template>
    </StatePanel>
    <StatePanel
      v-else-if="status === 'error'"
      as="h1"
      tone="error"
      :icon="mdiAlertCircleOutline"
      title="Couldn't load this list"
      :text="errorMessage(page.loadError.value)"
    >
      <template #actions>
        <v-btn color="primary" :prepend-icon="mdiRefresh" @click="page.load()">Try again</v-btn>
      </template>
    </StatePanel>

    <!-- The list -->
    <template v-else-if="list">
      <ListHeader
        :list="list"
        :link-count="links.length"
        :can-edit="isOwner"
        :can="page.can"
        :sign-in-to-copy="signInToCopy"
        :rename="rename"
        @share="shareOpen = true"
        @leave="leaveOpen = true"
        @delete="deleteListOpen = true"
        @copy="startCopy"
        @report="reportOpen = true"
      />

      <!-- Editors: add a link -->
      <AddLinkCard v-if="isOwner" :count="links.length" :submit="addLink" />

      <!-- Links -->
      <section aria-labelledby="links-heading">
        <ListToolbar
          v-model:search="search"
          v-model:sort="sort"
          v-model:view="view"
          :count="links.length"
        />

        <LinkCollection
          v-if="visibleLinks.length"
          :links="visibleLinks"
          :view="view"
          :can-edit="isOwner"
          :reorderable="reorderable"
          :can-move-to-list="canMoveToList"
          @details="detailsId = $event.id"
          @edit="editingId = $event.id"
          @delete="deleting = $event"
          @move="moveLink"
          @move-to-position="positionId = $event.id"
          @move-to-list="pickerId = $event.id"
        />
        <StatePanel
          v-else-if="links.length"
          :icon="mdiMagnify"
          title="No matching links"
          :text="`Nothing in this list matches “${search}”.`"
        >
          <template #actions>
            <v-btn variant="tonal" color="primary" @click="search = ''">Clear search</v-btn>
          </template>
        </StatePanel>
        <StatePanel
          v-else-if="isOwner"
          :icon="mdiPlus"
          title="Add your first link"
          text="Paste a link above. Each link gets a short URL you can share on its own."
        />
        <StatePanel
          v-else
          :icon="mdiLinkVariantPlus"
          title="Nothing here yet"
          text="The creator of this list hasn't added any links. Check back soon."
        />
      </section>
      <LiveRegion :message="announcement" />

      <!-- Dialogs -->
      <ShareDialog
        v-model="shareOpen"
        :title="list.title"
        :url="list.url"
        :visibility="list.visibility"
        :allow-fork="list.allow_fork"
        :can-change="page.can('settings')"
        :email-verified="Boolean(session.user.value?.email_verified)"
        :people="
          page.can('view_members')
            ? {
                code,
                ownerName: list.owner?.display_name || null,
                youAreOwner: list.my_role === 'owner',
                canManage: page.can('members'),
              }
            : undefined
        "
        @change-visibility="setVisibility"
        @change-allow-fork="setAllowFork"
      />
      <CopyListDialog v-model="copyOpen" :list="list" @copied="openCopy" />
      <ReportDialog
        v-if="page.can('report')"
        v-model="reportOpen"
        kind="list"
        :title="list.title"
        :send="sendReport"
        @sent="notify.success('Thanks. We\'ve received your report.')"
      />
      <LinkDetailsDialog
        v-model="detailsOpen"
        :link="byId(detailsId)"
        :refresh="isOwner ? () => page.refreshMetadata(detailsId!) : undefined"
      />
      <MovePositionDialog
        v-model="positionOpen"
        :title="positionLink ? shownTitle(positionLink) : ''"
        :position="positionLink ? links.indexOf(positionLink) + 1 : 1"
        :count="links.length"
        @move="positionLink && moveLink(positionLink, $event)"
      />
      <ListPickerDialog
        v-model="pickerOpen"
        :title="pickerLink ? shownTitle(pickerLink) : ''"
        :current-code="code"
        :move="moveToList"
      />
      <LinkEditDialog
        v-model="editOpen"
        :link="byId(editingId)"
        :can-upload="page.can('upload')"
        :submit="saveLink"
        :set-icon="setIcon"
      />
      <ConfirmDialog
        v-model="deleteOpen"
        title="Delete this link?"
        :text="`“${deleting?.title || deleting?.destination_url}” will be removed and its short link will stop working.`"
        action="Delete link"
        :on-confirm="confirmDeleteLink"
      />
      <ConfirmDialog
        v-model="deleteListOpen"
        title="Delete this list?"
        text="The list, all its links and their short links will be removed for everyone. This can't be undone."
        action="Delete list"
        :confirm-text="list.title"
        :on-confirm="confirmDeleteList"
      />
      <ConfirmDialog
        v-model="leaveOpen"
        title="Leave this list?"
        :text="
          list.visibility === 'private'
            ? 'You will no longer be able to open it. The owner can add you again.'
            : 'It will no longer appear in My lists. The owner can add you again.'
        "
        action="Leave list"
        :on-confirm="confirmLeave"
      />
    </template>
  </div>
</template>
