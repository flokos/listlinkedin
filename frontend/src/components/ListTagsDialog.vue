<script setup lang="ts">
// A list's tags (owners and editors). They aren't content: saving them adds no version.
import { ref, watch } from 'vue'

import { formErrors, noErrors } from '../utils/forms'
import TagsField from './TagsField.vue'

const open = defineModel<boolean>({ required: true })
const props = defineProps<{
  tags: string[]
  /** Public lists are listed in Explore, where tags help people find them. */
  isPublic: boolean
  /** Saves the tags; throws to show the error. */
  save: (tags: string[]) => Promise<unknown>
}>()

const FIELDS = ['tags'] as const
const chosen = ref<string[]>([])
const errors = ref(noErrors(FIELDS))
const busy = ref(false)
const field = ref<{ focus: () => void }>()

watch(
  open,
  (isOpen) => {
    if (!isOpen) return
    chosen.value = [...props.tags]
    errors.value = noErrors(FIELDS)
  },
  { immediate: true },
)

async function submit() {
  busy.value = true
  errors.value = noErrors(FIELDS)
  try {
    await props.save(chosen.value)
    open.value = false
  } catch (error) {
    errors.value = formErrors(error, FIELDS)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <v-dialog v-model="open" max-width="520" aria-label="Tags" @after-enter="field?.focus()">
    <v-card class="pa-2" title="Tags">
      <v-form @submit.prevent="submit">
        <v-card-text>
          <p class="text-body-medium text-medium-emphasis mb-4">
            {{
              isPublic
                ? 'This list is public: people can find it in Explore by its tags.'
                : 'Tags are shown on the list. They help people find it in Explore once it is public.'
            }}
          </p>
          <TagsField ref="field" v-model="chosen" :error-messages="errors.fields.tags" />
          <v-alert
            v-if="errors.form"
            type="error"
            density="compact"
            class="mt-3"
            :text="errors.form"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="open = false">Cancel</v-btn>
          <v-btn type="submit" color="primary" variant="flat" :loading="busy">Save tags</v-btn>
        </v-card-actions>
      </v-form>
    </v-card>
  </v-dialog>
</template>
