<script setup lang="ts">
import { mdiArrowRight } from '@mdi/js'
import { ref } from 'vue'

import { ApiError, createList, type CreatedList, errorMessage, LIMITS } from '../api'

defineProps<{ autofocus?: boolean }>()
const emit = defineEmits<{ created: [list: CreatedList] }>()

const title = ref('')
const error = ref<string[]>([])
const busy = ref(false)
const retryIn = ref(0)
let timer: ReturnType<typeof setInterval> | undefined

function countdown(seconds: number) {
  retryIn.value = seconds
  clearInterval(timer)
  timer = setInterval(() => {
    retryIn.value -= 1
    if (retryIn.value <= 0) {
      clearInterval(timer)
      error.value = []
    }
  }, 1000)
}

async function onSubmit() {
  const value = title.value.trim()
  if (!value) {
    error.value = ['Give your list a name.']
    return
  }
  busy.value = true
  error.value = []
  try {
    emit('created', await createList(value))
    title.value = ''
  } catch (e) {
    if (e instanceof ApiError && e.status === 429) {
      const wait = e.retryAfter ?? 60
      countdown(wait)
      error.value = [`You've created a lot of lists. Try again in ${Math.ceil(wait / 60)} min.`]
    } else {
      error.value =
        e instanceof ApiError ? (e.fieldErrors.title ?? [e.userMessage]) : [errorMessage(e)]
    }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <v-form class="ll-create" @submit.prevent="onSubmit">
    <label for="create-title" class="ll-sr-only">List name</label>
    <div class="ll-create__row">
      <v-text-field
        id="create-title"
        v-model="title"
        placeholder="Name your list, e.g. Friday team bonding"
        :maxlength="LIMITS.titleLength"
        :error-messages="error"
        :autofocus="autofocus"
        hide-details="auto"
        bg-color="surface"
        aria-label="List name"
        @update:model-value="retryIn > 0 || (error = [])"
      />
      <v-btn
        type="submit"
        color="primary"
        size="x-large"
        :loading="busy"
        :disabled="retryIn > 0"
        :append-icon="mdiArrowRight"
        class="ll-create__btn"
      >
        Create list
      </v-btn>
    </div>
    <p class="text-body-small text-medium-emphasis mt-2">
      Free, no sign-up. Lists expire after 30 days.
    </p>
  </v-form>
</template>

<style scoped>
.ll-create__row {
  display: grid;
  gap: 12px;
}
@media (min-width: 600px) {
  .ll-create__row {
    grid-template-columns: 1fr auto;
    align-items: start;
  }
  .ll-create__btn {
    height: 48px !important;
  }
}
</style>
