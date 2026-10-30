<script setup lang="ts">
// Tags for a list or group: type one and press Enter or comma; popular tags are offered.
// Tags are stored normalized ("Dev Tools" → "dev-tools"), so the chips show that form.
import { onMounted, ref } from 'vue'

import { normalizeTag, popularTags, TAG_LIMITS } from '../api'

const tags = defineModel<string[]>({ required: true })
defineProps<{ errorMessages?: string[] }>()

const box = ref<{ focus: () => void }>()
defineExpose({ focus: () => box.value?.focus() })

const suggestions = ref<string[]>([])
const search = ref('')

onMounted(async () => {
  try {
    suggestions.value = (await popularTags()).map((t) => t.tag)
  } catch {
    // Suggestions are optional: typing tags still works.
  }
})

function update(values: string[]) {
  const unique: string[] = []
  for (const value of values.flatMap((v) => v.split(','))) {
    const tag = normalizeTag(value)
    if (tag && !unique.includes(tag)) unique.push(tag)
  }
  tags.value = unique
  search.value = ''
}
</script>

<template>
  <v-combobox
    ref="box"
    v-model:search="search"
    :model-value="tags"
    :items="suggestions"
    label="Tags (optional)"
    multiple
    chips
    closable-chips
    hide-no-data
    :delimiters="[',']"
    :counter="TAG_LIMITS.perItem"
    :counter-value="tags.length"
    :error-messages="errorMessages"
    :hint="`Up to ${TAG_LIMITS.perItem} words like “dev-tools”. Public ones help people find it in Explore.`"
    persistent-hint
    @update:model-value="update"
  />
</template>
