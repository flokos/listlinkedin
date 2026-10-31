<script setup lang="ts">
// What one version changed compared with the version before it, then its full content.
import {
  mdiArrowUpDown,
  mdiMinusCircleOutline,
  mdiPencilOutline,
  mdiPlusCircleOutline,
} from '@mdi/js'
import { computed } from 'vue'

import type { LinkChangeKind, RevisionDetail } from '../api'
import { fieldName, linkName } from '../utils/history'

const props = defineProps<{ detail: RevisionDetail }>()

const listChanges = computed(() => Object.entries(props.detail.diff_from_previous.list))
const linkChanges = computed(() => props.detail.diff_from_previous.links)
const empty = computed(() => !listChanges.value.length && !linkChanges.value.length)

const LABELS: Record<LinkChangeKind, { text: string; icon: string; color: string }> = {
  added: { text: 'Added', icon: mdiPlusCircleOutline, color: 'success' },
  removed: { text: 'Removed', icon: mdiMinusCircleOutline, color: 'error' },
  modified: { text: 'Edited', icon: mdiPencilOutline, color: 'primary' },
  moved: { text: 'Moved', icon: mdiArrowUpDown, color: 'secondary' },
}
const shown = (value: string | null) => (value === null || value === '' ? '(none)' : value)
</script>

<template>
  <section aria-labelledby="changes-heading" class="mb-8">
    <h3 id="changes-heading" class="text-title-medium mb-3">Changes</h3>
    <p v-if="empty && detail.number === 1" class="text-body-medium text-medium-emphasis">
      The list's first version.
    </p>
    <p v-else-if="empty" class="text-body-medium text-medium-emphasis">No changes.</p>
    <ul v-else class="ll-changes">
      <li v-for="[field, change] in listChanges" :key="field" class="ll-change">
        <v-icon :icon="mdiPencilOutline" color="primary" size="20" aria-hidden="true" />
        <div>
          <span class="font-weight-medium">List {{ fieldName(field).toLowerCase() }} changed</span>
          <p class="text-body-small ma-0">
            <del>{{ shown(change.before) }}</del> → <ins>{{ shown(change.after) }}</ins>
          </p>
        </div>
      </li>
      <li v-for="change in linkChanges" :key="change.id" class="ll-change">
        <v-icon
          :icon="LABELS[change.changes[0]!].icon"
          :color="LABELS[change.changes[0]!].color"
          size="20"
          aria-hidden="true"
        />
        <div class="ll-change__body">
          <span class="font-weight-medium">{{ linkName(change) }}</span>
          <span class="text-body-small text-medium-emphasis">
            · {{ change.changes.map((c) => LABELS[c].text).join(', ') }}
            <template v-if="change.changes.includes('moved')">
              (to position {{ (change.position_after ?? 0) + 1 }})</template
            >
          </span>
          <p v-for="(values, field) in change.fields" :key="field" class="text-body-small ma-0">
            {{ fieldName(String(field)) }}: <del>{{ shown(values.before) }}</del> →
            <ins>{{ shown(values.after) }}</ins>
          </p>
        </div>
      </li>
    </ul>
  </section>

  <section aria-labelledby="content-heading">
    <h3 id="content-heading" class="text-title-medium mb-3">
      Links in this version ({{ detail.snapshot.links.length }})
    </h3>
    <p v-if="!detail.snapshot.links.length" class="text-body-medium text-medium-emphasis">
      No links.
    </p>
    <ol v-else class="ll-snapshot">
      <li v-for="link in detail.snapshot.links" :key="link.id">
        <span class="font-weight-medium">{{ linkName(link) }}</span>
        <span v-if="link.title" class="text-body-small text-medium-emphasis">
          · {{ link.url }}</span
        >
      </li>
    </ol>
  </section>
</template>

<style scoped>
.ll-changes {
  list-style: none;
  padding: 0;
  display: grid;
  gap: 12px;
}
.ll-change {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}
.ll-change__body,
.ll-snapshot li {
  min-width: 0;
  overflow-wrap: anywhere;
}
.ll-snapshot {
  padding-left: 1.5rem;
  display: grid;
  gap: 6px;
}
del {
  text-decoration: line-through;
}
ins {
  text-decoration: none;
  font-weight: 500;
}
</style>
