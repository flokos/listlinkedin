<script setup lang="ts">
// Live region for page changes; see composables/useRouteFocus.ts.
import { routeAnnouncement } from '../composables/useRouteFocus'
</script>

<template>
  <div class="ll-sr-only" role="status" aria-live="polite" aria-atomic="true">
    {{ routeAnnouncement }}
  </div>
</template>
