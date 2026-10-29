<script setup lang="ts">
// A link's picture: its uploaded icon, else the fetched one (both in `display.icon_url`, same
// origin), else the letter avatar. Decorative: the link's name is always next to it.
import { ref, watch } from 'vue'

import DomainAvatar from './DomainAvatar.vue'

const props = defineProps<{ url: string; iconUrl: string | null | undefined; size: number }>()
const broken = ref(false)
watch(
  () => props.iconUrl,
  () => (broken.value = false),
)
</script>

<template>
  <img
    v-if="iconUrl && !broken"
    :src="iconUrl"
    alt=""
    :width="size"
    :height="size"
    loading="lazy"
    decoding="async"
    class="ll-link-icon"
    @error="broken = true"
  />
  <DomainAvatar v-else :url="url" :size="size" />
</template>

<style scoped>
.ll-link-icon {
  flex-shrink: 0;
  object-fit: contain;
  border-radius: 12px;
}
</style>
