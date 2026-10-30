<script setup lang="ts">
// A link's picture: its uploaded icon, else the fetched one (both in `display.icon_url`, same
// origin), else the letter avatar. Decorative: the link's name is always next to it. While the
// page's details are being fetched (`pending`), it shimmers and says so to screen readers.
import { ref, watch } from 'vue'

import DomainAvatar from './DomainAvatar.vue'

const props = defineProps<{
  url: string
  iconUrl: string | null | undefined
  size: number
  pending?: boolean
}>()
const broken = ref(false)
watch(
  () => props.iconUrl,
  () => (broken.value = false),
)
</script>

<template>
  <span class="ll-link-icon__frame" :class="{ 'll-link-icon--pending': pending }">
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
    <span v-if="pending" class="ll-sr-only">Fetching details…</span>
  </span>
</template>

<style scoped>
.ll-link-icon__frame {
  position: relative;
  display: inline-flex;
  flex-shrink: 0;
  border-radius: 12px;
}
/* A soft sweep over the icon while its page is fetched (docs/v2/11 "Metadata in progress"). */
.ll-link-icon--pending::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(
    100deg,
    transparent 30%,
    rgba(var(--v-theme-surface), 0.55) 50%,
    transparent 70%
  );
  background-size: 250% 100%;
  animation: ll-icon-shimmer 1.4s linear infinite;
}
@keyframes ll-icon-shimmer {
  from {
    background-position: 150% 0;
  }
  to {
    background-position: -100% 0;
  }
}
@media (prefers-reduced-motion: reduce) {
  .ll-link-icon--pending::after {
    animation: none;
    background: rgba(var(--v-theme-surface), 0.35);
  }
}
.ll-link-icon {
  flex-shrink: 0;
  object-fit: contain;
  border-radius: 12px;
}
</style>
