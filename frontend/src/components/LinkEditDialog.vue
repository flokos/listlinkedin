<script setup lang="ts">
import type { LinkInput, SharedLink } from '../api'
import ImageUploadField from './ImageUploadField.vue'
import LinkForm from './LinkForm.vue'
import { ref } from 'vue'

const open = defineModel<boolean>({ required: true })
const props = defineProps<{
  link: SharedLink | null
  /** Shows the icon field (accounts only: an edit link can't upload). */
  canUpload: boolean
  submit: (input: LinkInput) => Promise<unknown>
  setIcon: (file: File | null) => Promise<unknown>
}>()

const form = ref<InstanceType<typeof LinkForm>>()

/** After the opening transition: focus the URL, unless the user already moved into the form
 * (an unconditional focus here typed their title into the URL, docs/v2/17 task 2.4). */
function focusUrl() {
  const active = document.activeElement
  if (active instanceof HTMLElement && active.closest('.ll-link-edit form')) return
  form.value?.focus()
}
</script>

<template>
  <v-dialog v-model="open" max-width="560" aria-label="Edit link" @after-enter="focusUrl">
    <v-card v-if="props.link" class="pa-2 ll-link-edit" title="Edit link">
      <v-card-text>
        <p class="text-body-small text-medium-emphasis mb-4">
          The short link stays the same, so anyone who has it will reach the new destination.
        </p>
        <LinkForm
          ref="form"
          mode="edit"
          :initial="{
            url: props.link.destination_url,
            title: props.link.title,
            description: props.link.description ?? null,
          }"
          :suggestions="props.link.fetched"
          :submit="submit"
          @done="open = false"
          @cancel="open = false"
        />
        <template v-if="canUpload">
          <v-divider class="my-5" />
          <ImageUploadField label="Icon" :image-url="props.link.icon_url ?? null" :save="setIcon" />
        </template>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>
