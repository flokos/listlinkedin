<script setup lang="ts">
// Choose, replace or remove an image (a link's icon now; the list image later). The server
// checks and re-encodes every file; this only gives quick feedback on size and type.
import { mdiDeleteOutline, mdiImagePlusOutline } from '@mdi/js'
import { ref } from 'vue'

import { errorMessage, LIMITS } from '../api'

const props = defineProps<{
  label: string
  /** The current image (same-origin URL), if any. */
  imageUrl: string | null
  /** Uploads the file, or removes the image with `null`. Throws on failure. */
  save: (file: File | null) => Promise<unknown>
}>()

const input = ref<HTMLInputElement>()
const busy = ref(false)
const error = ref<string>()
const ACCEPT = 'image/png,image/jpeg,image/webp,image/gif'

async function run(file: File | null) {
  error.value = undefined
  if (file && file.size > LIMITS.imageBytes) {
    error.value = 'Images can be at most 2 MB.'
    return
  }
  busy.value = true
  try {
    await props.save(file)
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
    if (input.value) input.value.value = ''
  }
}

function onChange(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) void run(file)
}
</script>

<template>
  <div class="ll-image-upload">
    <p class="text-label-large mb-2">{{ label }}</p>
    <div class="d-flex align-center flex-wrap ga-3">
      <img
        v-if="imageUrl"
        :src="imageUrl"
        alt=""
        width="56"
        height="56"
        class="ll-image-upload__preview"
      />
      <input
        ref="input"
        type="file"
        :accept="ACCEPT"
        class="ll-sr-only"
        :aria-label="`${imageUrl ? 'Replace' : 'Choose'} ${label.toLowerCase()}`"
        tabindex="-1"
        @change="onChange"
      />
      <v-btn
        variant="tonal"
        :prepend-icon="mdiImagePlusOutline"
        :loading="busy"
        @click="input?.click()"
      >
        {{ imageUrl ? 'Replace' : 'Choose image' }}
      </v-btn>
      <v-btn
        v-if="imageUrl"
        variant="text"
        :prepend-icon="mdiDeleteOutline"
        :disabled="busy"
        @click="run(null)"
      >
        Remove
      </v-btn>
    </div>
    <p class="text-body-small text-medium-emphasis mt-2 mb-0">
      PNG, JPEG, WebP or GIF, up to 2 MB.
    </p>
    <v-alert v-if="error" type="error" density="compact" class="mt-2" :text="error" />
  </div>
</template>

<style scoped>
.ll-image-upload__preview {
  object-fit: contain;
  border-radius: 12px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
</style>
