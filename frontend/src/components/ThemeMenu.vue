<script setup lang="ts">
import { mdiMonitor, mdiWeatherNight, mdiWhiteBalanceSunny } from '@mdi/js'
import { computed } from 'vue'

import { type ThemePreference, useThemePreference } from '../composables/useThemePreference'

const { preference } = useThemePreference()

const options: { value: ThemePreference; title: string; icon: string }[] = [
  { value: 'system', title: 'System', icon: mdiMonitor },
  { value: 'light', title: 'Light', icon: mdiWhiteBalanceSunny },
  { value: 'dark', title: 'Dark', icon: mdiWeatherNight },
]
const current = computed(() => options.find((o) => o.value === preference.value) ?? options[0]!)
</script>

<template>
  <v-menu>
    <template #activator="{ props }">
      <v-btn
        v-bind="props"
        :icon="current.icon"
        variant="text"
        :aria-label="`Theme: ${current.title}. Change theme`"
      />
    </template>
    <v-list density="compact" nav aria-label="Theme" role="menu">
      <v-list-item
        v-for="option in options"
        :key="option.value"
        role="menuitemradio"
        :aria-checked="option.value === preference"
        :title="option.title"
        :prepend-icon="option.icon"
        :active="option.value === preference"
        color="primary"
        @click="preference = option.value"
      />
    </v-list>
  </v-menu>
</template>
