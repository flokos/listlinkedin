<script setup lang="ts">
// The narrow centred column shared by the sign-in, sign-up and password pages.
defineProps<{ title: string; text?: string }>()
</script>

<template>
  <div class="ll-auth py-8 py-md-14">
    <h1 class="text-headline-large mb-2">{{ title }}</h1>
    <p v-if="text" class="text-body-large text-medium-emphasis mb-6">{{ text }}</p>
    <v-card class="pa-5 pa-sm-6">
      <slot />
    </v-card>
    <div v-if="$slots.footer" class="text-body-medium text-center mt-6">
      <slot name="footer" />
    </div>
  </div>
</template>

<style scoped>
.ll-auth {
  max-width: 440px;
  margin-inline: auto;
}
</style>
