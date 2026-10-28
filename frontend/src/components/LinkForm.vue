<script setup lang="ts">
// Add or edit a link. Validates like the server first, then maps server field errors
// (duplicate, blocked host…) onto the right field.
import { mdiPlus } from '@mdi/js'
import { computed, ref } from 'vue'

import { ApiError, errorMessage, LIMITS, type LinkInput } from '../api'
import { validateUrl, withScheme } from '../utils/url'

const props = defineProps<{
  mode: 'add' | 'edit'
  initial?: { url: string; title: string | null }
  disabled?: boolean
  submit: (input: LinkInput) => Promise<unknown>
}>()
const emit = defineEmits<{ done: []; cancel: [] }>()

const url = ref(props.initial?.url ?? '')
const title = ref(props.initial?.title ?? '')
const urlError = ref<string[]>([])
const titleError = ref<string[]>([])
const formError = ref<string>()
const busy = ref(false)
const urlField = ref<{ focus: () => void }>()

const unchanged = computed(
  () =>
    props.mode === 'edit' &&
    withScheme(url.value) === props.initial?.url &&
    (title.value.trim() || null) === (props.initial?.title ?? null),
)

async function onSubmit() {
  urlError.value = []
  titleError.value = []
  formError.value = undefined
  const destination = withScheme(url.value)
  const problem = validateUrl(destination)
  if (problem) {
    urlError.value = [problem]
    urlField.value?.focus()
    return
  }
  if (title.value.length > LIMITS.titleLength) {
    titleError.value = [`Titles can be at most ${LIMITS.titleLength} characters.`]
    return
  }
  busy.value = true
  try {
    await props.submit({ destination_url: destination, title: title.value.trim() || null })
    if (props.mode === 'add') {
      url.value = ''
      title.value = ''
      urlField.value?.focus()
    }
    emit('done')
  } catch (error) {
    if (error instanceof ApiError && Object.keys(error.fieldErrors).length) {
      urlError.value = error.fieldErrors.destination_url ?? []
      titleError.value = error.fieldErrors.title ?? []
      const other = error.fieldErrors.non_field_errors ?? []
      if (!urlError.value.length && !titleError.value.length)
        formError.value = other[0] ?? error.userMessage
    } else {
      formError.value = errorMessage(error)
    }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <v-form :disabled="disabled" @submit.prevent="onSubmit">
    <div class="ll-link-form" :class="`ll-link-form--${mode}`">
      <v-text-field
        ref="urlField"
        v-model="url"
        label="Link"
        placeholder="https://example.com/article"
        type="url"
        inputmode="url"
        autocomplete="off"
        autocapitalize="off"
        spellcheck="false"
        :autofocus="mode === 'edit'"
        :error-messages="urlError"
        hide-details="auto"
        class="ll-link-form__url"
        @update:model-value="urlError = []"
      />
      <v-text-field
        v-model="title"
        label="Title (optional)"
        :counter="title.length > LIMITS.titleLength - 40 ? LIMITS.titleLength : undefined"
        :error-messages="titleError"
        hide-details="auto"
        class="ll-link-form__title"
        @update:model-value="titleError = []"
      />
      <div v-if="mode === 'add'" class="ll-link-form__submit">
        <v-btn
          type="submit"
          color="primary"
          size="large"
          :loading="busy"
          :prepend-icon="mdiPlus"
          block
        >
          Add link
        </v-btn>
      </div>
    </div>
    <v-alert v-if="formError" type="error" density="compact" class="mt-3" :text="formError" />
    <div v-if="mode === 'edit'" class="d-flex justify-end ga-2 mt-4">
      <v-btn variant="text" :disabled="busy" @click="emit('cancel')">Cancel</v-btn>
      <v-btn type="submit" color="primary" :loading="busy" :disabled="unchanged"
        >Save changes</v-btn
      >
    </div>
  </v-form>
</template>

<style scoped>
.ll-link-form {
  display: grid;
  gap: 12px;
}
.ll-link-form--add {
  grid-template-columns: 1fr;
}
@media (min-width: 960px) {
  .ll-link-form--add {
    grid-template-columns: minmax(0, 3fr) minmax(0, 2fr) auto;
    align-items: start;
  }
  .ll-link-form__submit .v-btn {
    height: 48px !important;
  }
}
</style>
