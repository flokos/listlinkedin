<script setup lang="ts">
// A list's history (/l/:code/history?v=N): its versions, what each changed, and restoring one
// (docs/v2/11-UI-UX-MIGRATION.md#copy-synced-copy-and-history). Editors, owners and a legacy
// list's edit link only; the server enforces it.
import {
  mdiAlertCircleOutline,
  mdiArrowLeft,
  mdiHistory,
  mdiLinkOff,
  mdiLockOutline,
  mdiRefresh,
} from '@mdi/js'
import { computed, ref, toRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  ApiError,
  errorMessage,
  getRevision,
  listRevisions,
  restoreRevision,
  type Revision,
  type RevisionDetail,
} from '../api'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import HistoryTimeline from '../components/HistoryTimeline.vue'
import RevisionDiff from '../components/RevisionDiff.vue'
import StatePanel from '../components/StatePanel.vue'
import { useListPage } from '../composables/useListPage'
import { useNotify } from '../composables/useNotify'
import { describeRevision } from '../utils/history'
import { formatDate } from '../utils/time'

const props = defineProps<{ code: string }>()
const route = useRoute()
const router = useRouter()
const notify = useNotify()
const page = useListPage(toRef(props, 'code'))
const { list, status, token } = page

const revisions = ref<Revision[]>([])
const nextPage = ref<number | null>(1)
const historyError = ref<unknown>()
const detail = ref<RevisionDetail>()
const detailError = ref<unknown>()
const head = computed(() => list.value?.head_revision ?? 0)
const selected = computed(() => {
  const n = Number(route.query.v)
  return Number.isInteger(n) && n >= 1 ? n : head.value || undefined
})

async function loadHistory(reset = false) {
  if (reset) {
    revisions.value = []
    nextPage.value = 1
  }
  if (nextPage.value === null) return
  try {
    const result = await listRevisions(props.code, nextPage.value, token.value)
    revisions.value = [...revisions.value, ...result.results]
    nextPage.value = result.next ? nextPage.value + 1 : null
    historyError.value = undefined
  } catch (error) {
    historyError.value = error
  }
}

watch(
  [() => list.value?.code, () => list.value?.permissions.includes('view_history')],
  ([code, allowed]) => {
    if (code && allowed && !revisions.value.length) void loadHistory(true)
  },
  { immediate: true },
)

watch(
  [selected, () => props.code],
  async ([number]) => {
    detail.value = undefined
    detailError.value = undefined
    if (!number || !list.value?.permissions.includes('view_history')) return
    try {
      detail.value = await getRevision(props.code, number, token.value)
    } catch (error) {
      detailError.value = error
    }
  },
  { immediate: true },
)
watch(list, () => {
  if (selected.value && !detail.value && !detailError.value) {
    void getRevision(props.code, selected.value, token.value).then(
      (d) => (detail.value = d),
      (e) => (detailError.value = e),
    )
  }
})

watch(
  list,
  (value) => {
    if (value) document.title = `History of ${value.title} · listlinkedin`
  },
  { immediate: true },
)

const canRestore = computed(
  () => page.can('edit') && detail.value !== undefined && detail.value.number !== head.value,
)
const restoreOpen = ref(false)
async function confirmRestore() {
  if (!detail.value) return
  const number = detail.value.number
  try {
    const result = await restoreRevision(props.code, number, head.value, token.value)
    notify.success(
      result.changed
        ? `Restored version ${number}. It is now version ${result.revision}.`
        : 'The list already has this content.',
    )
    await page.load()
    await loadHistory(true)
    await router.replace({ query: { v: result.revision } })
  } catch (error) {
    if (error instanceof ApiError && error.status === 412) {
      notify.error('This list changed meanwhile. The latest history is shown now.')
      await page.load()
      await loadHistory(true)
      return
    }
    notify.error(errorMessage(error))
    throw error
  }
}
</script>

<template>
  <div class="ll-content py-6 py-md-10">
    <v-btn
      :prepend-icon="mdiArrowLeft"
      variant="text"
      class="mb-4 ml-n3"
      :to="{ name: 'list', params: { code } }"
    >
      {{ list?.title ?? 'Back to the list' }}
    </v-btn>

    <div v-if="status === 'loading'" aria-busy="true" aria-label="Loading history">
      <v-skeleton-loader type="heading" class="mb-6" max-width="320" />
      <v-skeleton-loader v-for="n in 4" :key="n" type="list-item-two-line" />
    </div>
    <StatePanel
      v-else-if="status === 'not-found'"
      as="h1"
      :icon="mdiLinkOff"
      title="This list doesn't exist"
      text="It may have been deleted, the link is mistyped, or it isn't shared with you."
    />
    <StatePanel
      v-else-if="status === 'expired'"
      as="h1"
      tone="warning"
      :icon="mdiAlertCircleOutline"
      title="This list has expired"
    />
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

    <template v-else-if="list">
      <StatePanel
        v-if="!page.can('view_history')"
        as="h1"
        :icon="mdiLockOutline"
        title="Only the list's editors can see its history"
        text="History can include links that were deliberately removed."
      />
      <template v-else>
        <header class="mb-6">
          <h1 class="text-headline-large d-flex align-center ga-3">
            <v-icon :icon="mdiHistory" color="primary" aria-hidden="true" /> History
          </h1>
          <p class="text-body-medium text-medium-emphasis mt-1">
            Every change to “{{ list.title }}” is kept as a version. Restoring one adds a new
            version; nothing is lost.
          </p>
        </header>

        <v-alert v-if="historyError" type="error" class="mb-4" :text="errorMessage(historyError)" />
        <div class="ll-history">
          <HistoryTimeline
            :revisions="revisions"
            :selected="selected"
            :head="head"
            :more="nextPage !== null && revisions.length > 0"
            class="ll-history__timeline"
            @more="loadHistory()"
          />

          <section class="ll-history__detail" aria-labelledby="version-heading">
            <v-alert
              v-if="detailError"
              type="error"
              :text="
                detailError instanceof ApiError && detailError.status === 404
                  ? 'This version doesn\'t exist.'
                  : errorMessage(detailError)
              "
            />
            <div v-else-if="!detail" aria-busy="true" aria-label="Loading version">
              <v-skeleton-loader type="heading, paragraph" />
            </div>
            <template v-else>
              <div class="d-flex flex-wrap align-start justify-space-between ga-3 mb-4">
                <div>
                  <h2 id="version-heading" class="text-title-large">
                    Version {{ detail.number }}
                    <span v-if="detail.number === head" class="text-medium-emphasis"
                      >(current)</span
                    >
                  </h2>
                  <p class="text-body-small text-medium-emphasis ma-0">
                    {{ describeRevision(detail) }} · {{ formatDate(detail.created_at) }}
                  </p>
                </div>
                <v-btn v-if="canRestore" color="primary" @click="restoreOpen = true">
                  Restore this version
                </v-btn>
              </div>
              <RevisionDiff :detail="detail" />
            </template>
          </section>
        </div>

        <ConfirmDialog
          v-model="restoreOpen"
          :title="`Restore version ${detail?.number}?`"
          :text="`Creates version ${head + 1} with this content. Nothing is lost: the current version stays in the history.`"
          action="Restore this version"
          tone="neutral"
          :on-confirm="confirmRestore"
        />
      </template>
    </template>
  </div>
</template>

<style scoped>
.ll-history {
  display: grid;
  gap: 24px;
}
@media (min-width: 960px) {
  .ll-history {
    grid-template-columns: minmax(260px, 2fr) minmax(0, 3fr);
    align-items: start;
  }
  .ll-history__timeline {
    position: sticky;
    top: 80px;
  }
}
.ll-history__detail {
  min-width: 0;
}
</style>
