<script setup lang="ts">
// Brand mark: a link glyph on a violet-to-orchid tile, plus the wordmark.
// (The browser favicon is intentionally kept blue; this is the in-app mark.)
withDefaults(defineProps<{ size?: number; wordmark?: boolean }>(), { size: 32, wordmark: true })
</script>

<template>
  <span class="ll-logo d-inline-flex align-center ga-2">
    <svg :width="size" :height="size" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="ll-logo-gradient" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#7A35E3" />
          <stop offset="1" stop-color="#B02CA3" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="url(#ll-logo-gradient)" />
      <path
        fill="#fff"
        d="M14.1 17.9a1.3 1.3 0 0 0 1.9 0l4-4a2.7 2.7 0 0 0-3.8-3.8l-.9.9-1.9-1.9.9-.9a5.4 5.4 0 0 1 7.6 7.6l-4 4a4 4 0 0 1-5.7 0zm3.8-3.8a1.3 1.3 0 0 0-1.9 0l-4 4a2.7 2.7 0 0 0 3.8 3.8l.9-.9 1.9 1.9-.9.9a5.4 5.4 0 0 1-7.6-7.6l4-4a4 4 0 0 1 5.7 0z"
      />
    </svg>
    <span v-if="wordmark" class="ll-logo__word text-title-large">
      list<span class="text-primary">linked</span>in
    </span>
  </span>
</template>

<style scoped>
.ll-logo__word {
  font-weight: 750 !important;
  letter-spacing: -0.03em !important;
  color: rgb(var(--v-theme-on-surface));
}
</style>
