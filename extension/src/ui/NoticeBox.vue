<script setup lang="ts">
// A message about what just happened. Errors interrupt a screen reader; the rest wait their turn.
defineProps<{ tone: 'info' | 'success' | 'warning' | 'error' }>()
</script>

<template>
  <div
    class="ll-notice"
    :class="`ll-notice--${tone}`"
    :role="tone === 'error' ? 'alert' : 'status'"
  >
    <slot />
  </div>
</template>

<style scoped>
.ll-notice {
  padding: 10px 12px;
  border-radius: var(--ll-radius);
  overflow-wrap: anywhere;
}
.ll-notice--info {
  background: var(--ll-info-container);
  color: var(--ll-on-info-container);
}
.ll-notice--success {
  background: var(--ll-success-container);
  color: var(--ll-on-success-container);
}
.ll-notice--warning {
  background: var(--ll-warning-container);
  color: var(--ll-on-warning-container);
}
.ll-notice--error {
  background: var(--ll-error-container);
  color: var(--ll-on-error-container);
}
</style>
