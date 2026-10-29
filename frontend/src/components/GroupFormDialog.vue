<script setup lang="ts">
// A group's name, description and image: "New group" (no `group` yet) or its Settings.
// Who can see the group is chosen in the Share dialog, as for lists.
import { computed, ref, watch } from 'vue'

import { type GroupDetail, type GroupInput, LIMITS } from '../api'
import { formErrors, noErrors } from '../utils/forms'
import ImageUploadField from './ImageUploadField.vue'

const open = defineModel<boolean>({ required: true })
const props = defineProps<{
  /** The group being changed; none for a new group. */
  group?: GroupDetail | null
  /** Saves the fields; throws to show the errors. */
  submit: (input: GroupInput) => Promise<unknown>
  /** Uploads the image, or removes it with `null` (settings only, for group editors). */
  setImage?: (file: File | null) => Promise<unknown>
}>()

const FIELDS = ['title', 'description'] as const
const title = ref('')
const description = ref('')
const errors = ref(noErrors(FIELDS))
const busy = ref(false)
const isNew = computed(() => !props.group)

watch(open, (isOpen) => {
  if (!isOpen) return
  title.value = props.group?.title ?? ''
  description.value = props.group?.description ?? ''
  errors.value = noErrors(FIELDS)
})

async function save() {
  errors.value = noErrors(FIELDS)
  const name = title.value.trim()
  if (!name) {
    errors.value.fields.title = ['Give your group a name.']
    return
  }
  busy.value = true
  try {
    await props.submit({ title: name, description: description.value.trim() })
    open.value = false
  } catch (error) {
    errors.value = formErrors(error, FIELDS)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <v-dialog
    v-model="open"
    max-width="520"
    scrollable
    :aria-label="isNew ? 'New group' : 'Group settings'"
  >
    <v-card class="pa-2" :title="isNew ? 'New group' : 'Group settings'">
      <v-form @submit.prevent="save">
        <v-card-text>
          <p v-if="isNew" class="text-body-medium text-medium-emphasis mb-4">
            A group collects lists in one place with a sidebar. It starts private: only people you
            add can open it.
          </p>
          <v-text-field
            v-model="title"
            label="Name"
            :maxlength="LIMITS.titleLength"
            :error-messages="errors.fields.title"
            autofocus
            @update:model-value="errors.fields.title = []"
          />
          <v-textarea
            v-model="description"
            label="Description (optional)"
            rows="3"
            auto-grow
            :maxlength="LIMITS.descriptionLength"
            :error-messages="errors.fields.description"
            class="mt-2"
          />
          <ImageUploadField
            v-if="group && setImage"
            label="Image"
            :image-url="group.image_url"
            :save="setImage"
            class="mt-2"
          />
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
          <v-btn type="submit" color="primary" variant="flat" :loading="busy">
            {{ isNew ? 'Create group' : 'Save' }}
          </v-btn>
        </v-card-actions>
      </v-form>
    </v-card>
  </v-dialog>
</template>
