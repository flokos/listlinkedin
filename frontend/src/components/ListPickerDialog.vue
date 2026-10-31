<script setup lang="ts">
// "Move to another list…": pick one of your lists you can edit. The link is copied there
// (with a new short link) and deleted here, in one step on the server.
import { mdiFormatListBulleted } from '@mdi/js'
import { ref, watch } from 'vue'

import { errorMessage, LIMITS, myLists, type ListDetail } from '../api'

const open = defineModel<boolean>({ required: true })
const props = defineProps<{
  /** The link being moved, for the heading. */
  title: string
  /** The current list, which isn't offered. */
  currentCode: string
  /** Moves the link; throws to show why it can't go there. */
  move: (target: ListDetail) => Promise<unknown>
}>()

const lists = ref<ListDetail[]>()
const loadError = ref<string>()
const moveError = ref<string>()
const busy = ref<string>()

watch(open, async (isOpen) => {
  if (!isOpen) return
  lists.value = undefined
  loadError.value = moveError.value = undefined
  try {
    const page = await myLists()
    lists.value = page.results.filter(
      (l) => l.code !== props.currentCode && l.permissions.includes('edit'),
    )
  } catch (error) {
    loadError.value = errorMessage(error)
  }
})

async function choose(target: ListDetail) {
  busy.value = target.code
  moveError.value = undefined
  try {
    await props.move(target)
    open.value = false
  } catch (error) {
    moveError.value = errorMessage(error)
  } finally {
    busy.value = undefined
  }
}
</script>

<template>
  <v-dialog v-model="open" max-width="480" scrollable aria-label="Move to another list">
    <v-card class="pa-2" title="Move to another list">
      <v-card-text>
        <p class="text-body-medium mb-4">
          “{{ title }}” moves to the end of the list you choose and gets a new short link there. Its
          current short link stops working.
        </p>
        <v-alert v-if="loadError" type="error" density="compact" :text="loadError" />
        <v-progress-linear v-else-if="!lists" indeterminate aria-label="Loading your lists" />
        <p v-else-if="!lists.length" class="text-body-medium text-medium-emphasis">
          You have no other lists you can add links to.
        </p>
        <v-list v-else density="comfortable" aria-label="Your lists" class="pa-0">
          <v-list-item
            v-for="target in lists"
            :key="target.code"
            :prepend-icon="mdiFormatListBulleted"
            :title="target.title"
            :subtitle="`${target.link_count} link${target.link_count === 1 ? '' : 's'}`"
            :disabled="Boolean(busy) || target.link_count >= LIMITS.linksPerList"
            rounded="lg"
            @click="choose(target)"
          >
            <template #append>
              <v-progress-circular v-if="busy === target.code" indeterminate size="20" />
              <span
                v-else-if="target.link_count >= LIMITS.linksPerList"
                class="text-body-small text-medium-emphasis"
                >Full</span
              >
            </template>
          </v-list-item>
        </v-list>
        <v-alert v-if="moveError" type="error" density="compact" class="mt-3" :text="moveError" />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="open = false">Cancel</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
