<script setup lang="ts">
// Regain edit access by pasting an edit link (or a bare owner token for a known list).
import { mdiKeyOutline } from '@mdi/js'
import { ref, watch } from 'vue'

import { ApiError, errorMessage, verifyOwnership } from '../api'
import { parseEditInput } from '../composables/useEditLink'
import { useOwnedLists } from '../composables/useOwnedLists'

const open = defineModel<boolean>({ required: true })
const props = defineProps<{ code?: string }>()
const emit = defineEmits<{ claimed: [code: string] }>()

const input = ref('')
const error = ref<string[]>([])
const busy = ref(false)
const owned = useOwnedLists()

watch(open, (value) => {
  if (value) {
    input.value = ''
    error.value = []
  }
})

async function submit() {
  const parsed = parseEditInput(input.value)
  const code = parsed?.code ?? props.code
  if (!parsed || !code) {
    error.value = [props.code ? 'Paste the edit link (or its token).' : 'Paste the full edit link.']
    return
  }
  if (props.code && parsed.code && parsed.code !== props.code) {
    error.value = ['That edit link belongs to a different list.']
    return
  }
  busy.value = true
  try {
    const list = await verifyOwnership(code, parsed.token)
    owned.save({ code, token: parsed.token, title: list.title, expiresAt: list.expires_at })
    open.value = false
    emit('claimed', code)
  } catch (e) {
    error.value = [
      e instanceof ApiError && (e.status === 401 || e.status === 403)
        ? "That edit link doesn't work. It may have been replaced by a newer one."
        : errorMessage(e),
    ]
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <v-dialog v-model="open" max-width="520">
    <v-card class="pa-2">
      <v-card-item :prepend-icon="mdiKeyOutline">
        <v-card-title class="text-title-large">Open with an edit link</v-card-title>
      </v-card-item>
      <v-card-text class="pt-4">
        <p class="text-body-medium mb-4">
          Paste the private edit link you saved when the list was created. It will be remembered in
          this browser.
        </p>
        <v-form @submit.prevent="submit">
          <v-text-field
            v-model="input"
            label="Edit link"
            placeholder="https://…/l/…/manage#t=…"
            autocomplete="off"
            spellcheck="false"
            autofocus
            :error-messages="error"
            @update:model-value="error = []"
          />
        </v-form>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="open = false">Cancel</v-btn>
        <v-btn color="primary" :loading="busy" @click="submit">Unlock editing</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
