<script setup lang="ts">
import {
  mdiAlertCircleOutline,
  mdiArrowLeft,
  mdiCalendarRemoveOutline,
  mdiCheck,
  mdiClose,
  mdiDeleteOutline,
  mdiDotsVertical,
  mdiKeyChange,
  mdiKeyOutline,
  mdiLinkOff,
  mdiLinkVariantPlus,
  mdiMagnify,
  mdiPencilOutline,
  mdiPlus,
  mdiRefresh,
  mdiShareVariant,
  mdiShieldKeyOutline,
  mdiTrayRemove,
} from '@mdi/js'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, toRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { errorMessage, LIMITS, type SharedLink } from '../api'
import ClaimTokenDialog from '../components/ClaimTokenDialog.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import EditLinkReveal from '../components/EditLinkReveal.vue'
import ExpiryChip from '../components/ExpiryChip.vue'
import LinkCard from '../components/LinkCard.vue'
import LinkForm from '../components/LinkForm.vue'
import LinkLimitMeter from '../components/LinkLimitMeter.vue'
import ShareDialog from '../components/ShareDialog.vue'
import StatePanel from '../components/StatePanel.vue'
import { useListPage } from '../composables/useListPage'
import { useNotify } from '../composables/useNotify'
import { usePendingReveal } from '../composables/usePendingReveal'
import { formatDate } from '../utils/time'

const props = defineProps<{ code: string }>()
const route = useRoute()
const router = useRouter()
const notify = useNotify()
const page = useListPage(toRef(props, 'code'))
const { list, links, status, isOwner, ownerRevoked, token } = page

// Title follows the list's name.
watch([list, status], ([value, state]) => {
  const titles: Partial<Record<typeof state, string>> = {
    'not-found': 'List not found',
    expired: 'List expired',
    error: "Couldn't load list",
  }
  const title = titles[state] ?? (state === 'ready' ? value?.title : undefined)
  if (title) document.title = `${title} · listlinkedin`
})

// Back link: to Saved lists when the user came from there.
const cameFromMyLists = computed(() =>
  String(window.history.state?.back ?? '').startsWith('/lists'),
)

// Search and sort (client-side: a list holds at most 100 links, all loaded at once).
const search = ref('')
const sort = ref<'newest' | 'az'>('newest')
const searchField = ref<{ focus: () => void }>()
const visibleLinks = computed(() => {
  const q = search.value.trim().toLowerCase()
  const matches = q
    ? links.value.filter((l) =>
        [l.title ?? '', l.destination_url].some((text) => text.toLowerCase().includes(q)),
      )
    : links.value
  if (sort.value === 'newest') return matches
  const key = (l: SharedLink) =>
    (l.title || l.destination_url.replace(/^https?:\/\/(www\.)?/, '')).toLowerCase()
  return [...matches].sort((a, b) => key(a).localeCompare(key(b)))
})
const atLimit = computed(() => links.value.length >= LIMITS.linksPerList)

// "/" focuses search, as in many web apps.
function onKeydown(event: KeyboardEvent) {
  const target = event.target as HTMLElement
  if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey) return
  if (target.closest('input, textarea, [contenteditable="true"]')) return
  if (links.value.length < 2) return
  event.preventDefault()
  searchField.value?.focus()
}
onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))

// Share dialog is reflected in the URL (?dialog=share) so the browser's Back button closes it.
const shareOpen = computed({
  get: () => route.query.dialog === 'share',
  set: (value) => {
    if (value) router.push({ query: { ...route.query, dialog: 'share' } })
    else if (route.query.dialog === 'share') router.back()
  },
})

// Edit link reveal: right after creation (handed over by Home), after rotation, or on demand.
const reveal = ref<{ open: boolean; mode: 'created' | 'rotated' | 'view' }>({
  open: false,
  mode: 'view',
})
const pending = usePendingReveal()
watch(
  list,
  (value) => {
    if (value && pending.isPending(props.code)) reveal.value = { open: true, mode: 'created' }
  },
  { immediate: true },
)
// The created-list step counts as done once the user closes it (only possible after
// confirming they saved the link).
watch(
  () => reveal.value.open,
  (open) => {
    if (!open && reveal.value.mode === 'created') pending.clear()
  },
)

// Inline rename.
const renaming = ref(false)
const newTitle = ref('')
const renameError = ref<string[]>([])
const renameBusy = ref(false)
const renameField = ref<{ focus: () => void }>()
async function startRename() {
  newTitle.value = list.value?.title ?? ''
  renameError.value = []
  renaming.value = true
  await nextTick()
  renameField.value?.focus()
}
async function saveRename() {
  const title = newTitle.value.trim()
  if (!title) {
    renameError.value = ['A list needs a name.']
    return
  }
  if (title === list.value?.title) {
    renaming.value = false
    return
  }
  renameBusy.value = true
  try {
    await page.rename(title)
    renaming.value = false
    notify.success('List renamed')
  } catch (error) {
    // Lost edit access: the banner explains it, so close the editor instead.
    if (ownerRevoked.value) renaming.value = false
    else renameError.value = [errorMessage(error)]
  } finally {
    renameBusy.value = false
  }
}

// Link editing and deletion.
const editing = ref<SharedLink | null>(null)
const editOpen = computed({
  get: () => editing.value !== null,
  set: (v) => !v && (editing.value = null),
})
const deleting = ref<SharedLink | null>(null)
const deleteOpen = computed({
  get: () => deleting.value !== null,
  set: (v) => !v && (deleting.value = null),
})

async function addLink(input: Parameters<typeof page.addLink>[0]) {
  await page.addLink(input)
  notify.success('Link added')
}
async function saveLink(input: Parameters<typeof page.editLink>[1]) {
  if (!editing.value) return
  await page.editLink(editing.value.id, input)
  notify.success('Link updated')
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
const rotateOpen = ref(false)
const deleteListOpen = ref(false)
const claimOpen = ref(false)

async function confirmRotate() {
  try {
    await page.rotate()
    reveal.value = { open: true, mode: 'rotated' }
  } catch (error) {
    notify.error(errorMessage(error))
    throw error
  }
}
async function confirmDeleteList() {
  try {
    await page.removeList()
    notify.success('List deleted')
    router.replace({ name: 'saved-lists' })
  } catch (error) {
    notify.error(errorMessage(error))
    throw error
  }
}
function forgetHere() {
  page.forget()
  notify.info('This browser no longer has edit access to the list')
}
</script>

<template>
  <div class="ll-content py-6 py-md-10">
    <v-btn
      v-if="cameFromMyLists"
      :prepend-icon="mdiArrowLeft"
      variant="text"
      class="mb-4 ml-n3"
      @click="router.back()"
    >
      Saved lists
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
      text="It may have been deleted by its creator, or the link is mistyped."
    >
      <template #actions>
        <v-btn color="primary" :to="{ name: 'home', hash: '#create' }">Create a new list</v-btn>
      </template>
    </StatePanel>
    <StatePanel
      v-else-if="status === 'expired'"
      as="h1"
      tone="warning"
      :icon="mdiCalendarRemoveOutline"
      title="This list has expired"
      text="Lists are available for 30 days. This one has reached the end of its life, and its short links no longer work."
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
      <header class="ll-list-header mb-6">
        <div class="d-flex flex-wrap align-start ga-4">
          <div class="flex-grow-1 ll-list-header__main">
            <p class="text-label-large text-primary mb-1">
              {{ isOwner ? 'Your list' : 'Shared list' }}
            </p>
            <v-form v-if="renaming" class="d-flex align-start ga-2" @submit.prevent="saveRename">
              <v-text-field
                ref="renameField"
                v-model="newTitle"
                label="List name"
                :maxlength="LIMITS.titleLength"
                :error-messages="renameError"
                hide-details="auto"
                class="flex-grow-1"
                @keydown.esc="renaming = false"
              />
              <v-btn
                type="submit"
                :icon="mdiCheck"
                color="primary"
                :loading="renameBusy"
                aria-label="Save name"
              />
              <v-btn
                :icon="mdiClose"
                variant="text"
                aria-label="Cancel renaming"
                @click="renaming = false"
              />
            </v-form>
            <h1 v-else class="text-headline-large ll-list-title">
              {{ list.title }}
              <v-btn
                v-if="isOwner"
                icon
                variant="text"
                density="comfortable"
                class="ll-list-title__edit"
                aria-label="Rename list"
                @click="startRename"
              >
                <v-icon :icon="mdiPencilOutline" size="20" />
              </v-btn>
            </h1>
            <div class="d-flex flex-wrap align-center ga-2 mt-3">
              <ExpiryChip :expires-at="list.expires_at" />
              <v-chip color="secondary"
                >{{ links.length }} link{{ links.length === 1 ? '' : 's' }}</v-chip
              >
              <span class="text-body-small text-medium-emphasis"
                >Created {{ formatDate(list.created_at) }}</span
              >
            </div>
          </div>

          <div class="d-flex align-center ga-1">
            <v-btn
              color="primary"
              :variant="isOwner ? 'tonal' : 'flat'"
              :prepend-icon="mdiShareVariant"
              @click="shareOpen = true"
            >
              Share
            </v-btn>
            <v-menu v-if="isOwner" location="bottom end">
              <template #activator="{ props: menu }">
                <v-btn
                  v-bind="menu"
                  :icon="mdiDotsVertical"
                  variant="text"
                  aria-label="List options"
                />
              </template>
              <v-list role="menu" density="comfortable" nav min-width="240">
                <v-list-item
                  role="menuitem"
                  :prepend-icon="mdiPencilOutline"
                  title="Rename"
                  @click="startRename"
                />
                <v-list-item
                  role="menuitem"
                  :prepend-icon="mdiShieldKeyOutline"
                  title="Show edit link"
                  @click="reveal = { open: true, mode: 'view' }"
                />
                <v-list-item
                  role="menuitem"
                  :prepend-icon="mdiKeyChange"
                  title="Replace edit link"
                  @click="rotateOpen = true"
                />
                <v-divider class="my-1" />
                <v-list-item
                  role="menuitem"
                  :prepend-icon="mdiTrayRemove"
                  title="Forget on this device"
                  @click="forgetHere"
                />
                <v-list-item
                  role="menuitem"
                  :prepend-icon="mdiDeleteOutline"
                  title="Delete list"
                  base-color="error"
                  @click="deleteListOpen = true"
                />
              </v-list>
            </v-menu>
          </div>
        </div>
      </header>

      <v-alert
        v-if="ownerRevoked"
        type="warning"
        class="mb-6"
        title="Your edit link was replaced"
        text="This browser's edit link no longer works, probably because a new one was created. Paste the new edit link to keep editing."
      >
        <template #append>
          <div class="d-flex flex-column flex-sm-row ga-2">
            <v-btn variant="flat" color="warning" @click="claimOpen = true">Paste edit link</v-btn>
            <v-btn variant="text" @click="forgetHere">Forget</v-btn>
          </div>
        </template>
      </v-alert>

      <!-- Owner: add a link -->
      <v-card v-if="isOwner" class="pa-4 pa-sm-5 mb-8 ll-add-card" color="surface-container">
        <div class="d-flex flex-wrap align-center justify-space-between ga-4 mb-4">
          <h2 class="text-title-large d-flex align-center ga-2">
            <v-icon :icon="mdiLinkVariantPlus" color="primary" /> Add a link
          </h2>
          <LinkLimitMeter :count="links.length" />
        </div>
        <v-alert
          v-if="atLimit"
          type="info"
          density="compact"
          class="mb-3"
          text="This list has reached its limit of 100 links. Delete one to add another."
        />
        <LinkForm mode="add" :disabled="atLimit" :submit="addLink" />
      </v-card>

      <!-- Links -->
      <section aria-labelledby="links-heading">
        <div class="d-flex flex-wrap align-center ga-3 mb-4">
          <h2 id="links-heading" class="text-title-large flex-grow-1">Links</h2>
          <template v-if="links.length > 1">
            <v-text-field
              ref="searchField"
              v-model="search"
              :prepend-inner-icon="mdiMagnify"
              placeholder="Search links"
              aria-label="Search links"
              density="compact"
              hide-details
              clearable
              class="ll-search"
            >
              <template #append-inner>
                <kbd
                  v-if="!search"
                  class="ll-kbd d-none d-md-inline-block"
                  title="Press / to search"
                  >/</kbd
                >
              </template>
            </v-text-field>
            <v-btn-toggle
              v-model="sort"
              mandatory
              variant="outlined"
              density="compact"
              aria-label="Sort links"
            >
              <v-btn value="newest">Newest</v-btn>
              <v-btn value="az">A–Z</v-btn>
            </v-btn-toggle>
          </template>
        </div>

        <TransitionGroup
          v-if="visibleLinks.length"
          name="ll-list"
          tag="div"
          class="d-flex flex-column ga-3"
        >
          <LinkCard
            v-for="link in visibleLinks"
            :key="link.id"
            :link="link"
            :owner="isOwner"
            @edit="editing = link"
            @delete="deleting = link"
          />
        </TransitionGroup>
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
        >
          <template #actions>
            <v-btn variant="text" :prepend-icon="mdiKeyOutline" @click="claimOpen = true"
              >I have the edit link</v-btn
            >
          </template>
        </StatePanel>
      </section>

      <p v-if="!isOwner && links.length && !ownerRevoked" class="text-center mt-10">
        <v-btn variant="text" size="small" :prepend-icon="mdiKeyOutline" @click="claimOpen = true">
          Created this list? Open it with your edit link
        </v-btn>
      </p>

      <!-- Dialogs -->
      <ShareDialog v-model="shareOpen" :title="list.title" :url="list.public_url" />
      <EditLinkReveal
        v-if="token"
        v-model="reveal.open"
        :mode="reveal.mode"
        :code="code"
        :token="token"
        :title="list.title"
        :public-url="list.public_url"
      />
      <v-dialog v-model="editOpen" max-width="560" aria-label="Edit link">
        <v-card v-if="editing" class="pa-2" title="Edit link">
          <v-card-text>
            <p class="text-body-small text-medium-emphasis mb-4">
              The short link stays the same, so anyone who has it will reach the new destination.
            </p>
            <LinkForm
              mode="edit"
              :initial="{ url: editing.destination_url, title: editing.title }"
              :submit="saveLink"
              @done="editing = null"
              @cancel="editing = null"
            />
          </v-card-text>
        </v-card>
      </v-dialog>
      <ConfirmDialog
        v-model="deleteOpen"
        title="Delete this link?"
        :text="`“${deleting?.title || deleting?.destination_url}” will be removed and its short link will stop working.`"
        action="Delete link"
        :on-confirm="confirmDeleteLink"
      />
      <ConfirmDialog
        v-model="rotateOpen"
        title="Replace the edit link?"
        text="You'll get a new edit link. The current one, including copies you've saved or shared, will stop working immediately."
        action="Replace edit link"
        :on-confirm="confirmRotate"
      />
      <ConfirmDialog
        v-model="deleteListOpen"
        title="Delete this list?"
        text="The list, all its links and their short links will be removed for everyone. This can't be undone."
        action="Delete list"
        :confirm-text="list.title"
        :on-confirm="confirmDeleteList"
      />
      <ClaimTokenDialog v-model="claimOpen" :code="code" @claimed="page.load()" />
    </template>
  </div>
</template>

<style scoped>
.ll-list-header__main {
  min-width: 0;
  flex-basis: 320px;
}
.ll-list-title {
  overflow-wrap: anywhere;
}
.ll-list-title__edit {
  vertical-align: middle;
  opacity: 0.6;
}
.ll-list-title__edit:hover,
.ll-list-title__edit:focus-visible {
  opacity: 1;
}
.ll-add-card {
  border-color: rgba(var(--v-theme-primary), 0.25) !important;
}
.ll-kbd {
  padding: 0 6px;
  border-radius: 4px;
  border: 1px solid rgba(var(--v-border-color), 0.3);
  font-family: var(--ll-font-mono);
  font-size: 0.75rem;
  line-height: 1.4;
  opacity: var(--v-medium-emphasis-opacity);
}
.ll-search {
  max-width: 280px;
  min-width: 180px;
}
.ll-list-enter-active,
.ll-list-leave-active {
  transition:
    opacity var(--ll-duration-base) var(--ll-ease-standard),
    transform var(--ll-duration-base) var(--ll-ease-standard);
}
.ll-list-enter-from {
  opacity: 0;
  transform: translateY(-8px);
}
.ll-list-leave-to {
  opacity: 0;
  transform: translateX(16px);
}
.ll-list-move {
  transition: transform var(--ll-duration-base) var(--ll-ease-standard);
}
</style>
