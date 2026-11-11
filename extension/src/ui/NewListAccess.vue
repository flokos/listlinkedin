<script setup lang="ts">
// "Who can open it" for a list that is about to be made. A new list is private unless the
// user chooses otherwise here (D16); the answer chosen last is offered again. The sentence
// under it says what the choice means for the list's link.
import { computed } from 'vue'

import type { Visibility } from '../lib/storage'
import { VISIBILITIES, VISIBILITY, whoCanOpen } from '../lib/visibility'

const props = defineProps<{ id: string; disabled?: boolean }>()
const choice = defineModel<Visibility>({ required: true })
const meaning = computed(() =>
  choice.value === 'private'
    ? 'Only you, until you add people on listlinkedin.'
    : whoCanOpen(choice.value, 'list', true),
)
</script>

<template>
  <div class="ll-field">
    <label :for="props.id">Who can open it</label>
    <select
      :id="props.id"
      v-model="choice"
      class="ll-input"
      :disabled="props.disabled"
      :aria-describedby="`${props.id}-meaning`"
    >
      <option v-for="value in VISIBILITIES" :key="value" :value="value">
        {{ VISIBILITY[value] }}
      </option>
    </select>
    <p :id="`${props.id}-meaning`" class="ll-muted">{{ meaning }}</p>
  </div>
</template>
