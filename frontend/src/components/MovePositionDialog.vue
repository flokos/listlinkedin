<script setup lang="ts">
// "Move to position…": type a place (1 to count) instead of moving one step at a time.
import { ref, watch } from 'vue'

const open = defineModel<boolean>({ required: true })
const props = defineProps<{ title: string; position: number; count: number }>()
const emit = defineEmits<{ move: [index: number] }>()

const value = ref('')
const field = ref<{ focus: () => void }>()
const error = ref<string[]>([])
watch(open, (isOpen) => {
  if (isOpen) {
    value.value = String(props.position)
    error.value = []
  }
})

function submit() {
  const n = Number(value.value)
  if (!Number.isInteger(n) || n < 1 || n > props.count) {
    error.value = [`Enter a number from 1 to ${props.count}.`]
    return
  }
  // Report before closing: closing clears which link the page is moving.
  if (n !== props.position) emit('move', n - 1)
  open.value = false
}
</script>

<template>
  <!-- Focus after opening, not with `autofocus` (it fires late; see LinkEditDialog). -->
  <v-dialog
    v-model="open"
    max-width="400"
    aria-label="Move to position"
    @after-enter="field?.focus()"
  >
    <v-card class="pa-2" title="Move to position">
      <v-form @submit.prevent="submit">
        <v-card-text>
          <p class="text-body-medium mb-4">
            Where should “{{ title }}” go? It is now number {{ position }} of {{ count }}.
          </p>
          <v-text-field
            ref="field"
            v-model="value"
            label="Position"
            type="number"
            inputmode="numeric"
            :min="1"
            :max="count"
            :error-messages="error"
            hide-details="auto"
            @update:model-value="error = []"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="open = false">Cancel</v-btn>
          <v-btn type="submit" color="primary" variant="flat">Move</v-btn>
        </v-card-actions>
      </v-form>
    </v-card>
  </v-dialog>
</template>
