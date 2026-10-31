<script setup lang="ts">
// A group's workspace (docs/v2/11-UI-UX-MIGRATION.md#groups-workspace): the sidebar of its
// lists and the chosen list, at /g/{code}/l/{listCode} so the URL keeps the choice and Back
// works. /g/{code}/{slug} shows the first list. The page stays mounted while switching lists
// (the route's pageKey); only the list part is replaced.
//
// The server sends only the lists this viewer may see (docs/v2/12-AUTHORIZATION.md), so
// nothing here hides or counts anything itself.
import {
  mdiAlertCircleOutline,
  mdiDeleteOutline,
  mdiDotsVertical,
  mdiFlagOutline,
  mdiFolderMultipleOutline,
  mdiFolderOffOutline,
  mdiLogout,
  mdiMenu,
  mdiPlus,
  mdiRefresh,
  mdiShareVariant,
  mdiSortVariant,
  mdiTuneVariant,
} from '@mdi/js'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDisplay } from 'vuetify'

import {
  addGroupList,
  ApiError,
  changeGroup,
  errorMessage,
  getGroup,
  type GroupDetail,
  type GroupInput,
  type GroupList,
  groupLists,
  type ListDetail,
  removeGroup,
  removeGroupImage,
  removeGroupList,
  removeMember,
  reorderGroupLists,
  reportGroup,
  type ReportInput,
  uploadGroupImage,
  type Visibility,
} from '../api'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import GroupAddListDialog from '../components/GroupAddListDialog.vue'
import GroupFormDialog from '../components/GroupFormDialog.vue'
import GroupSidebar, { type SidebarMode } from '../components/GroupSidebar.vue'
import LiveRegion from '../components/LiveRegion.vue'
import ReportDialog from '../components/ReportDialog.vue'
import ShareDialog from '../components/ShareDialog.vue'
import StatePanel from '../components/StatePanel.vue'
import { useNotify } from '../composables/useNotify'
import { useQueryDialog } from '../composables/useQueryDialog'
import { useSession } from '../composables/useSession'
import ListView from './ListView.vue'

const props = defineProps<{ code: string; slug?: string; listCode?: string }>()
const route = useRoute()
const router = useRouter()
const notify = useNotify()
const session = useSession()
const { width } = useDisplay()

const group = ref<GroupDetail | null>(null)
const lists = ref<GroupList[]>([])
const status = ref<'loading' | 'ready' | 'not-found' | 'error'>('loading')
const loadError = ref<unknown>()

async function load() {
  status.value = 'loading'
  try {
    const [detail, items] = await Promise.all([getGroup(props.code), groupLists(props.code)])
    group.value = detail
    lists.value = items
    status.value = 'ready'
  } catch (error) {
    loadError.value = error
    status.value = error instanceof ApiError && error.status === 404 ? 'not-found' : 'error'
  }
}
void load()

const can = (permission: string) => Boolean(group.value?.permissions.includes(permission))

// The list shown: the one in the URL, else the first.
const currentCode = computed(() => props.listCode ?? lists.value[0]?.code)
const currentInGroup = computed(() => lists.value.some((l) => l.code === currentCode.value))

// The page title: the list sets it (with the group's name) once it has loaded.
watch([group, status, currentInGroup], ([value, state, hasList]) => {
  if (state === 'not-found') document.title = 'Group not found · listlinkedin'
  else if (state === 'error') document.title = "Couldn't load group · listlinkedin"
  else if (value && !hasList) document.title = `${value.title} · listlinkedin`
})

// The sidebar: permanent from 1280 px, a rail from 960 px, a modal drawer below.
const mode = computed<SidebarMode>(() =>
  width.value >= 1280 ? 'permanent' : width.value >= 960 ? 'rail' : 'temporary',
)
const drawerOpen = ref(mode.value !== 'temporary')
watch(mode, (value) => (drawerOpen.value = value !== 'temporary'))
const reordering = ref(false)

// Keeping the sidebar in step with the list shown: a rename, a deletion, leaving it.
function onListLoaded(list: ListDetail) {
  lists.value = lists.value.map((l) => (l.code === list.code ? { ...l, title: list.title } : l))
}
async function onListGone() {
  lists.value = lists.value.filter((l) => l.code !== currentCode.value)
  await router.replace({ name: 'group', params: { code: props.code, slug: group.value?.slug } })
  void refreshLists()
}
async function refreshLists() {
  try {
    lists.value = await groupLists(props.code)
  } catch (error) {
    notify.error(errorMessage(error))
  }
}

// Reordering and removing, from the sidebar.
const moving = ref(false)
const announcement = ref<{ text: string } | null>(null)
async function moveList(item: GroupList, index: number) {
  moving.value = true
  try {
    lists.value = await reorderGroupLists(props.code, item.code, index)
    const at = lists.value.findIndex((l) => l.code === item.code) + 1
    announcement.value = { text: `${item.title} moved to position ${at} of ${lists.value.length}.` }
  } catch (error) {
    notify.error(errorMessage(error))
    void refreshLists() // show the order as it is
  } finally {
    moving.value = false
  }
}
async function takeOut(item: GroupList) {
  moving.value = true
  try {
    await removeGroupList(props.code, item.code)
    lists.value = lists.value.filter((l) => l.code !== item.code)
    if (group.value) group.value = { ...group.value, list_count: lists.value.length }
    notify.success(`Removed “${item.title}” from the group`)
    announcement.value = { text: `${item.title} removed from the group.` }
    if (item.code === props.listCode) {
      await router.replace({ name: 'group', params: { code: props.code, slug: group.value?.slug } })
    }
    if (lists.value.length < 2) reordering.value = false
  } catch (error) {
    notify.error(errorMessage(error))
  } finally {
    moving.value = false
  }
}

// Adding lists.
const addOpen = ref(false)
async function addList(listCode: string) {
  const item = await addGroupList(props.code, listCode)
  lists.value = [...lists.value, item]
  if (group.value) group.value = { ...group.value, list_count: lists.value.length }
  notify.success(`Added “${item.title}”`)
  return item
}

// Settings, sharing, leaving and deleting.
const settingsOpen = ref(false)
async function saveSettings(input: GroupInput) {
  group.value = await changeGroup(props.code, input)
  notify.success('Group updated')
}
async function setImage(file: File | null) {
  if (file) group.value = await uploadGroupImage(props.code, file)
  else {
    await removeGroupImage(props.code)
    if (group.value) group.value = { ...group.value, image_url: null }
  }
  notify.success(file ? 'Image updated' : 'Image removed')
}

const shareOpen = useQueryDialog('group-share')
async function setVisibility(visibility: Visibility) {
  try {
    group.value = await changeGroup(props.code, { visibility })
    notify.success('Sharing updated')
  } catch (error) {
    notify.error(errorMessage(error))
  }
}

// Anyone who can see the group, except its owner, may report it (task 9.0).
const reportOpen = ref(false)
const sendReport = (input: ReportInput) => reportGroup(props.code, input)

const deleteOpen = ref(false)
async function confirmDelete() {
  try {
    await removeGroup(props.code)
    notify.success('Group deleted')
    await router.replace({ name: 'groups' })
  } catch (error) {
    notify.error(errorMessage(error))
    throw error
  }
}
const leaveOpen = ref(false)
async function confirmLeave() {
  const me = session.user.value?.id
  if (!me) return
  try {
    await removeMember(props.code, me, 'group')
    notify.success(`You left “${group.value?.title}”`)
    await router.replace({ name: 'groups' })
  } catch (error) {
    notify.error(errorMessage(error))
    throw error
  }
}
</script>

<template>
  <div class="ll-group py-4 py-md-6">
    <!-- Loading -->
    <div v-if="status === 'loading'" aria-busy="true" aria-label="Loading group">
      <v-skeleton-loader type="heading" class="mb-6" max-width="360" />
      <v-skeleton-loader v-for="n in 3" :key="n" type="list-item-avatar-two-line" class="mb-2" />
    </div>

    <!-- Unavailable: the same for a missing group and one you may not see. -->
    <StatePanel
      v-else-if="status === 'not-found'"
      as="h1"
      :icon="mdiFolderOffOutline"
      title="This group doesn't exist"
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
          >Sign in</v-btn
        >
        <v-btn v-else color="primary" :to="{ name: 'groups' }">Your groups</v-btn>
      </template>
    </StatePanel>
    <StatePanel
      v-else-if="status === 'error'"
      as="h1"
      tone="error"
      :icon="mdiAlertCircleOutline"
      title="Couldn't load this group"
      :text="errorMessage(loadError)"
    >
      <template #actions>
        <v-btn color="primary" :prepend-icon="mdiRefresh" @click="load()">Try again</v-btn>
      </template>
    </StatePanel>

    <template v-else-if="group">
      <GroupSidebar
        v-model="drawerOpen"
        v-model:reordering="reordering"
        :mode="mode"
        :group-title="group.title"
        :group-code="code"
        :lists="lists"
        :current-code="currentInGroup ? currentCode : undefined"
        :can-edit="can('edit')"
        :busy="moving"
        @move="moveList"
        @remove="takeOut"
      />

      <!-- The group: its name, Share and ⋮. The list below has the page's <h1>, except in an
           empty group, where the group's name is the heading. -->
      <div class="ll-group__head d-flex align-center ga-2 mb-2">
        <v-btn
          v-if="mode === 'temporary'"
          :prepend-icon="mdiMenu"
          variant="tonal"
          :aria-label="`Lists in ${group.title}`"
          aria-haspopup="dialog"
          :aria-expanded="drawerOpen ? 'true' : 'false'"
          class="ll-group__lists-btn"
          @click="drawerOpen = true"
        >
          Lists
        </v-btn>
        <v-avatar v-if="group.image_url" :image="group.image_url" size="32" rounded="lg" />
        <v-icon v-else :icon="mdiFolderMultipleOutline" class="text-medium-emphasis" />
        <component
          :is="lists.length ? 'p' : 'h1'"
          class="ll-group__title text-title-large flex-grow-1"
        >
          {{ group.title }}
        </component>
        <v-btn
          :prepend-icon="mdiShareVariant"
          variant="tonal"
          color="primary"
          :aria-label="`Share the group ${group.title}`"
          @click="shareOpen = true"
          >Share</v-btn
        >
        <v-menu
          v-if="can('edit') || can('add_list') || can('leave') || can('delete') || can('report')"
          location="bottom end"
        >
          <template #activator="{ props: menu }">
            <v-btn
              v-bind="menu"
              :icon="mdiDotsVertical"
              variant="text"
              :aria-label="`More actions for the group ${group.title}`"
            />
          </template>
          <v-list role="menu" density="compact" nav>
            <v-list-item
              v-if="can('add_list')"
              role="menuitem"
              :prepend-icon="mdiPlus"
              title="Add lists"
              @click="addOpen = true"
            />
            <v-list-item
              v-if="can('edit') && lists.length > 1"
              role="menuitem"
              :prepend-icon="mdiSortVariant"
              title="Reorder lists"
              @click="reordering = true"
            />
            <v-list-item
              v-if="can('edit')"
              role="menuitem"
              :prepend-icon="mdiTuneVariant"
              title="Settings"
              @click="settingsOpen = true"
            />
            <v-list-item
              v-if="can('report')"
              role="menuitem"
              :prepend-icon="mdiFlagOutline"
              title="Report…"
              @click="reportOpen = true"
            />
            <v-list-item
              v-if="can('leave')"
              role="menuitem"
              :prepend-icon="mdiLogout"
              title="Leave group"
              @click="leaveOpen = true"
            />
            <v-list-item
              v-if="can('delete')"
              role="menuitem"
              :prepend-icon="mdiDeleteOutline"
              title="Delete group"
              base-color="error"
              @click="deleteOpen = true"
            />
          </v-list>
        </v-menu>
      </div>
      <p v-if="group.description && !lists.length" class="text-body-large text-medium-emphasis">
        {{ group.description }}
      </p>

      <ListView
        v-if="currentCode && currentInGroup"
        :key="currentCode"
        :code="currentCode"
        :in-group="{ title: group.title }"
        @loaded="onListLoaded"
        @gone="onListGone"
      />
      <StatePanel
        v-else-if="!lists.length"
        :icon="mdiFolderMultipleOutline"
        title="Add lists to build your workspace"
        :text="
          can('add_list')
            ? 'Add lists you own or edit, or public lists. Everyone sees only the lists they may open.'
            : 'There are no lists here for you yet.'
        "
      >
        <template v-if="can('add_list')" #actions>
          <v-btn color="primary" :prepend-icon="mdiPlus" @click="addOpen = true"
            >Add your first list</v-btn
          >
        </template>
      </StatePanel>
      <StatePanel
        v-else
        as="h1"
        :icon="mdiFolderOffOutline"
        title="This list isn't in the group"
        text="It may have been taken out of the group, or it isn't shared with you."
      >
        <template #actions>
          <v-btn color="primary" :to="{ name: 'group', params: { code, slug: group.slug } }" replace
            >Open the group's first list</v-btn
          >
        </template>
      </StatePanel>
      <LiveRegion :message="announcement" />

      <!-- Dialogs -->
      <ShareDialog
        v-model="shareOpen"
        kind="group"
        :title="group.title"
        :url="group.url"
        :visibility="group.visibility"
        :can-change="can('settings')"
        :email-verified="Boolean(session.user.value?.email_verified)"
        :people="
          can('view_members')
            ? {
                code,
                ownerName: group.owner?.display_name || null,
                youAreOwner: group.my_role === 'owner',
                canManage: can('members'),
              }
            : undefined
        "
        @change-visibility="setVisibility"
      />
      <GroupAddListDialog
        v-model="addOpen"
        :group-title="group.title"
        :in-group="lists.map((l) => l.code)"
        :add="addList"
      />
      <ReportDialog
        v-if="can('report')"
        v-model="reportOpen"
        kind="group"
        :title="group.title"
        :send="sendReport"
        @sent="notify.success('Thanks. We\'ve received your report.')"
      />
      <GroupFormDialog
        v-model="settingsOpen"
        :group="group"
        :submit="saveSettings"
        :set-image="setImage"
      />
      <ConfirmDialog
        v-model="deleteOpen"
        title="Delete this group?"
        text="The group goes away for everyone. The lists in it aren't changed or deleted."
        action="Delete group"
        :confirm-text="group.title"
        :on-confirm="confirmDelete"
      />
      <ConfirmDialog
        v-model="leaveOpen"
        title="Leave this group?"
        text="It will no longer appear in your groups. The owner can add you again."
        action="Leave group"
        :on-confirm="confirmLeave"
      />
    </template>
  </div>
</template>

<style scoped>
.ll-group {
  max-width: 1200px;
  margin-inline: auto;
}
.ll-group__title {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
}
</style>
