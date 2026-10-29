<script setup lang="ts">
import { mdiWifiOff } from '@mdi/js'
import { ref } from 'vue'

import AppFooter from './components/AppFooter.vue'
import AppHeader from './components/AppHeader.vue'
import AppNavDrawer from './components/AppNavDrawer.vue'
import RouteAnnouncer from './components/RouteAnnouncer.vue'
import RouteProgress from './components/RouteProgress.vue'
import { useNotify } from './composables/useNotify'
import { useOnline } from './composables/useOnline'
import { useThemePreference } from './composables/useThemePreference'

useThemePreference() // apply the saved light/dark choice before first paint
const drawer = ref(false)
const online = useOnline()
const { queue } = useNotify()
</script>

<template>
  <v-app>
    <a href="#main" class="ll-skip-link text-label-large">Skip to content</a>
    <RouteProgress />
    <AppHeader @toggle-drawer="drawer = !drawer" />
    <AppNavDrawer v-model="drawer" />

    <v-main id="main" tabindex="-1" class="d-flex flex-column">
      <v-banner
        v-if="!online"
        :icon="mdiWifiOff"
        color="warning"
        bg-color="warning-container"
        lines="one"
        role="status"
        text="You're offline. Changes can't be saved until you reconnect."
        sticky
      />
      <div class="flex-grow-1 px-4">
        <router-view v-slot="{ Component, route }">
          <!-- No <transition>: the previous page is replaced at once and the new one fades in
               with a CSS animation (.ll-page). Vue transitions wait on animation frames,
               which WebKit may not run in background tabs, leaving two pages mounted. -->
          <component
            :is="Component"
            :key="route.meta.pageKey?.(route) ?? route.path"
            class="ll-page"
          />
        </router-view>
      </div>
      <AppFooter />
    </v-main>

    <RouteAnnouncer />
    <v-snackbar-queue v-model="queue" closable="Dismiss" />
  </v-app>
</template>
