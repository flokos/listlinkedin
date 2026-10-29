<script setup lang="ts">
// Download all saved edit links as one file, or restore them from such a file (or from the
// .txt saved when a list was created). Every restored link is checked with the server first.
import { mdiDownload, mdiShieldAlertOutline, mdiUpload } from '@mdi/js'
import { computed, ref } from 'vue'

import { ApiError, verifyOwnership } from '../api'
import { useNotify } from '../composables/useNotify'
import { useOwnedLists } from '../composables/useOwnedLists'
import { backupFilename, createBackup, parseBackup } from '../utils/backup'
import { downloadText } from '../utils/download'

const owned = useOwnedLists()
const notify = useNotify()
const fileInput = ref<HTMLInputElement>()
const busy = ref(false)
const summary = ref<{ type: 'success' | 'warning' | 'error'; title: string; lines: string[] }>()

const hasLists = computed(() => owned.count.value > 0)

function download() {
  const backup = createBackup(owned.lists.value)
  downloadText(backupFilename(), JSON.stringify(backup, null, 2))
  notify.success(
    `Backup of ${backup.lists.length} list${backup.lists.length === 1 ? '' : 's'} downloaded`,
  )
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

async function restore(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = '' // allow choosing the same file again
  if (!file) return
  summary.value = undefined

  const entries = file.size > 1_000_000 ? [] : parseBackup(await file.text())
  if (!entries.length) {
    summary.value = {
      type: 'error',
      title: 'No lists found in that file',
      lines: ['Choose a listlinkedin backup (.json) or a file containing edit links.'],
    }
    return
  }

  busy.value = true
  const counts = { added: 0, already: 0, expired: 0, deleted: 0, replaced: 0, failed: 0 }
  // One at a time: a backup holds a handful of lists, and this stays well inside rate limits.
  for (const entry of entries) {
    if (owned.tokenFor(entry.code) === entry.token) {
      counts.already++
      continue
    }
    try {
      const list = await verifyOwnership(entry.code, entry.token)
      owned.save({
        code: entry.code,
        token: entry.token,
        title: list.title,
        expiresAt: list.expires_at ?? '',
      })
      counts.added++
    } catch (error) {
      const status = error instanceof ApiError ? error.status : 0
      if (status === 410) counts.expired++
      else if (status === 404) counts.deleted++
      else if (status === 401 || status === 403) counts.replaced++
      else counts.failed++
    }
  }
  busy.value = false

  // Singular/plural sentences: "1 list has expired", "2 lists have expired".
  const say = (n: number, one: string, many: string) =>
    n && (n === 1 ? one : many.replace('{n}', String(n)))
  const lines = [
    say(counts.already, '1 list is already saved here.', '{n} lists are already saved here.'),
    say(
      counts.expired,
      "1 list has expired and can't be restored.",
      "{n} lists have expired and can't be restored.",
    ),
    say(counts.deleted, '1 list no longer exists.', '{n} lists no longer exist.'),
    say(
      counts.replaced,
      '1 edit link was replaced after the backup and no longer works.',
      '{n} edit links were replaced after the backup and no longer work.',
    ),
    say(
      counts.failed,
      "1 list couldn't be checked. Try again later.",
      "{n} lists couldn't be checked. Try again later.",
    ),
  ].filter((line): line is string => Boolean(line))

  const problems = counts.expired + counts.deleted + counts.replaced + counts.failed
  summary.value = {
    type: counts.added ? (problems ? 'warning' : 'success') : problems ? 'error' : 'success',
    title: counts.added ? `Restored ${plural(counts.added, 'list')}` : 'Nothing new to restore',
    lines,
  }
  if (counts.added) notify.success(`Restored ${plural(counts.added, 'list')}`)
}
</script>

<template>
  <v-card class="pa-5" color="surface-container">
    <h2 class="text-title-large mb-1">Back up or move your saved lists</h2>
    <p class="text-body-medium text-medium-emphasis mb-4">
      There are no accounts, so your edit access lives in this browser. Download a backup to keep it
      safe or to restore it on another device. You can also restore from the edit-link file you
      saved when creating a list.
    </p>

    <div class="d-flex flex-wrap ga-3">
      <v-btn
        color="primary"
        variant="tonal"
        :prepend-icon="mdiDownload"
        :disabled="!hasLists"
        @click="download"
      >
        Download backup
      </v-btn>
      <v-btn
        variant="outlined"
        color="primary"
        :prepend-icon="mdiUpload"
        :loading="busy"
        @click="fileInput?.click()"
      >
        Restore from file
      </v-btn>
      <input
        ref="fileInput"
        type="file"
        accept=".json,.txt,application/json,text/plain"
        class="d-none"
        aria-label="Backup file"
        @change="restore"
      />
    </div>

    <p class="d-flex align-start ga-2 text-body-small text-medium-emphasis mt-4 mb-0">
      <v-icon :icon="mdiShieldAlertOutline" size="18" class="mt-px" />
      Keep the backup private: anyone with the file can change or delete these lists.
    </p>

    <v-alert
      v-if="summary"
      :type="summary.type"
      :title="summary.title"
      density="compact"
      class="mt-4"
      closable
      role="status"
      @click:close="summary = undefined"
    >
      <ul v-if="summary.lines.length" class="pl-4 mt-1">
        <li v-for="line in summary.lines" :key="line">{{ line }}</li>
      </ul>
    </v-alert>
  </v-card>
</template>
