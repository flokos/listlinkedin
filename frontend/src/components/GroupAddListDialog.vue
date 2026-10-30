<script setup lang="ts">
// "Add list": your lists you own or edit, and your public lists, plus any list by its link
// (a public list someone else made). The server decides: a list you may not share answers
// with the reason, and one you can't see answers "not found", whatever it is.
import { mdiCheck, mdiFormatListBulleted, mdiPlus } from '@mdi/js'
import { computed, ref, watch } from 'vue'

import { errorMessage, type GroupList, type ListDetail, myLists } from '../api'
import { listCodeFrom } from '../utils/url'

const open = defineModel<boolean>({ required: true })
const props = defineProps<{
  groupTitle: string
  /** Lists already in the group (as you see it), which aren't offered again. */
  inGroup: string[]
  /** Adds the list by its code; throws to show why it can't be added. */
  add: (listCode: string) => Promise<GroupList>
}>()

const lists = ref<ListDetail[]>()
const loadError = ref<string>()
const addError = ref<string>()
const busy = ref<string>()
const pasted = ref('')
const pastedError = ref<string[]>([])

watch(open, async (isOpen) => {
  if (!isOpen) return
  lists.value = undefined
  loadError.value = addError.value = undefined
  pasted.value = ''
  pastedError.value = []
  try {
    const page = await myLists()
    lists.value = page.results.filter(
      (l) => l.my_role === 'owner' || l.my_role === 'editor' || l.visibility === 'public',
    )
  } catch (error) {
    loadError.value = errorMessage(error)
  }
})

const added = computed(() => new Set(props.inGroup))

async function choose(code: string) {
  busy.value = code
  addError.value = undefined
  try {
    await props.add(code)
    return true
  } catch (error) {
    addError.value = errorMessage(error)
    return false
  } finally {
    busy.value = undefined
  }
}

async function addPasted() {
  pastedError.value = []
  const code = listCodeFrom(pasted.value)
  if (!code) {
    pastedError.value = ['Paste the link of a list, like https://…/l/abc123.']
    return
  }
  if (added.value.has(code)) {
    pastedError.value = ['This list is in the group already.']
    return
  }
  if (await choose(code)) pasted.value = ''
}
</script>

<template>
  <v-dialog v-model="open" max-width="520" scrollable aria-label="Add lists to the group">
    <v-card class="pa-2" title="Add lists" :subtitle="groupTitle">
      <v-card-text>
        <p class="text-body-medium mb-4">
          Each list keeps its own sharing: people who open the group see only the lists they may
          see.
        </p>
        <v-alert v-if="loadError" type="error" density="compact" :text="loadError" />
        <v-progress-linear v-else-if="!lists" indeterminate aria-label="Loading your lists" />
        <p v-else-if="!lists.length" class="text-body-medium text-medium-emphasis">
          You have no lists to add yet. Lists you own or edit appear here.
        </p>
        <v-list v-else density="comfortable" aria-label="Your lists" class="pa-0">
          <v-list-item
            v-for="item in lists"
            :key="item.code"
            :prepend-icon="mdiFormatListBulleted"
            :title="item.title"
            :subtitle="`${item.link_count} link${item.link_count === 1 ? '' : 's'}`"
            :disabled="Boolean(busy) && !added.has(item.code)"
            :link="!added.has(item.code)"
            rounded="lg"
            @click="!added.has(item.code) && choose(item.code)"
          >
            <template #append>
              <v-progress-circular v-if="busy === item.code" indeterminate size="20" />
              <span
                v-else-if="added.has(item.code)"
                class="d-flex align-center ga-1 text-body-small text-medium-emphasis"
              >
                <v-icon :icon="mdiCheck" size="18" /> In this group
              </span>
            </template>
          </v-list-item>
        </v-list>

        <v-form class="mt-6" @submit.prevent="addPasted">
          <div class="d-flex align-start ga-2">
            <v-text-field
              v-model="pasted"
              label="Or paste a list's link"
              hint="A public list, or one shared with you that you can edit."
              persistent-hint
              autocomplete="off"
              :error-messages="pastedError"
              :disabled="Boolean(busy)"
              @update:model-value="pastedError = []"
            />
            <v-btn
              type="submit"
              color="primary"
              variant="tonal"
              size="large"
              :prepend-icon="mdiPlus"
              :loading="Boolean(busy) && busy === listCodeFrom(pasted)"
              class="mt-1"
              >Add</v-btn
            >
          </div>
        </v-form>
        <v-alert
          v-if="addError"
          type="error"
          density="compact"
          class="mt-3"
          role="alert"
          :text="addError"
        />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="open = false">Done</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
