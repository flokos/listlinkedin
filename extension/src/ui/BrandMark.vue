<script setup lang="ts">
// The listlinkedin mark, as in the web app (frontend/src/components/AppLogo.vue).
withDefaults(defineProps<{ size?: number }>(), { size: 24 })
</script>

<template>
  <span class="ll-brand">
    <svg :width="size" :height="size" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="ll-brand-gradient" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#7A35E3" />
          <stop offset="1" stop-color="#B02CA3" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="url(#ll-brand-gradient)" />
      <path
        fill="#fff"
        d="M14.1 17.9a1.3 1.3 0 0 0 1.9 0l4-4a2.7 2.7 0 0 0-3.8-3.8l-.9.9-1.9-1.9.9-.9a5.4 5.4 0 0 1 7.6 7.6l-4 4a4 4 0 0 1-5.7 0zm3.8-3.8a1.3 1.3 0 0 0-1.9 0l-4 4a2.7 2.7 0 0 0 3.8 3.8l.9-.9 1.9 1.9-.9.9a5.4 5.4 0 0 1-7.6-7.6l4-4a4 4 0 0 1 5.7 0z"
      />
    </svg>
    <span class="ll-brand__word">list<span class="ll-brand__accent">linked</span>in</span>
  </span>
</template>

<style scoped>
.ll-brand {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.ll-brand__word {
  font-size: 16px;
  font-weight: 750;
  letter-spacing: -0.03em;
}
.ll-brand__accent {
  color: var(--ll-primary);
}
</style>
