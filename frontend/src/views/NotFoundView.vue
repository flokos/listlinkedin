<script setup lang="ts">
import { mdiCompassOffOutline } from '@mdi/js'

import StatePanel from '../components/StatePanel.vue'
</script>

<template>
  <div class="ll-content py-10">
    <StatePanel
      as="h1"
      :icon="mdiCompassOffOutline"
      title="Page not found"
      text="The page you're looking for doesn't exist. If someone sent you a list, check that you copied the whole link."
    >
      <template #actions>
        <v-btn color="primary" :to="{ name: 'home' }">Go home</v-btn>
        <v-btn variant="tonal" color="primary" :to="{ name: 'my-lists' }">My lists</v-btn>
      </template>
    </StatePanel>
  </div>
</template>
