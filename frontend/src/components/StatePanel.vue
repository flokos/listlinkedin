<script setup lang="ts">
// Empty and error states: one consistent layout with an icon, a message and next actions.
defineProps<{
  icon: string
  title: string
  text?: string
  tone?: 'neutral' | 'error' | 'warning'
  /** Heading level: h1 when the state replaces a whole page. */
  as?: 'h1' | 'h2'
}>()
</script>

<template>
  <section class="ll-state text-center py-12 px-4">
    <div class="ll-state__icon mx-auto mb-5" :class="`ll-state__icon--${tone ?? 'neutral'}`">
      <v-icon :icon="icon" size="32" />
    </div>
    <component :is="as ?? 'h2'" class="text-headline-small mb-2">{{ title }}</component>
    <p
      v-if="text || $slots.default"
      class="text-body-large text-medium-emphasis mx-auto ll-state__text"
    >
      <slot>{{ text }}</slot>
    </p>
    <div v-if="$slots.actions" class="d-flex flex-wrap justify-center ga-3 mt-6">
      <slot name="actions" />
    </div>
  </section>
</template>

<style scoped>
.ll-state__icon {
  display: grid;
  place-items: center;
  width: 72px;
  height: 72px;
  border-radius: 24px;
}
.ll-state__icon--neutral {
  background: rgb(var(--v-theme-primary-container));
  color: rgb(var(--v-theme-on-primary-container));
}
.ll-state__icon--error {
  background: rgb(var(--v-theme-error-container));
  color: rgb(var(--v-theme-on-error-container));
}
.ll-state__icon--warning {
  background: rgb(var(--v-theme-warning-container));
  color: rgb(var(--v-theme-on-warning-container));
}
.ll-state__text {
  max-width: 480px;
}
</style>
