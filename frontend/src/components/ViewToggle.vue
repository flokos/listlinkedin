<script setup lang="ts">
import { mdiViewAgendaOutline, mdiViewGridOutline } from '@mdi/js'

import type { LinkView } from '../composables/useViewPreference'

const view = defineModel<LinkView>({ required: true })
</script>

<template>
  <v-btn-toggle v-model="view" mandatory variant="outlined" density="compact" aria-label="Layout">
    <v-btn value="grid" :icon="mdiViewGridOutline" aria-label="Grid view" />
    <v-btn value="list" :icon="mdiViewAgendaOutline" aria-label="List view" />
  </v-btn-toggle>
</template>
