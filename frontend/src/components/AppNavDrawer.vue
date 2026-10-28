<script setup lang="ts">
import { mdiOpenInNew, mdiPlus } from '@mdi/js'
import { nextTick, onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'

import { useOwnedLists } from '../composables/useOwnedLists'
import { externalNav, mainNav } from '../navigation'
import AppLogo from './AppLogo.vue'

const open = defineModel<boolean>({ required: true })
const route = useRoute()
const { lists, count } = useOwnedLists()
const close = () => (open.value = false)

// Modal drawer behaviour: Escape closes it, focus moves in on open and back to the menu
// button on close.
let opener: HTMLElement | null = null
function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') close()
}
watch(open, async (value) => {
  if (value) {
    opener = document.activeElement as HTMLElement | null
    window.addEventListener('keydown', onKeydown)
    await nextTick()
    // After the slide-in transition starts; focusing a hidden element is a no-op.
    setTimeout(() => document.querySelector<HTMLElement>('.ll-nav-drawer a[href]')?.focus(), 150)
  } else {
    window.removeEventListener('keydown', onKeydown)
    opener?.focus()
  }
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <v-navigation-drawer
    v-model="open"
    class="ll-nav-drawer"
    temporary
    width="300"
    :role="open ? 'dialog' : undefined"
    :aria-modal="open ? 'true' : undefined"
    aria-label="Menu"
  >
    <div class="pa-4 pb-2"><AppLogo :size="28" /></div>
    <v-list nav aria-label="Main">
      <v-list-item
        v-for="item in mainNav"
        :key="item.label"
        :to="item.to"
        :prepend-icon="item.icon"
        :title="item.label"
        :active="item.match.includes(String(route.name))"
        color="primary"
        @click="close"
      >
        <template v-if="item.badge && count" #append>
          <v-badge :content="count" inline color="primary-container" />
        </template>
      </v-list-item>
      <v-list-item
        :to="{ name: 'home', hash: '#create' }"
        :prepend-icon="mdiPlus"
        title="New list"
        base-color="primary"
        @click="close"
      />
    </v-list>

    <template v-if="lists.length">
      <v-divider class="mx-4" />
      <v-list nav density="compact" aria-label="Lists on this device">
        <v-list-subheader>On this device</v-list-subheader>
        <v-list-item
          v-for="item in lists.slice(0, 5)"
          :key="item.code"
          :to="{ name: 'list', params: { code: item.code } }"
          :title="item.title || 'Untitled list'"
          @click="close"
        />
      </v-list>
    </template>

    <template #append>
      <v-list nav density="compact">
        <v-list-item
          v-for="link in externalNav"
          :key="link.label"
          :href="link.href"
          target="_blank"
          rel="noopener noreferrer"
          :title="link.label"
          :append-icon="mdiOpenInNew"
        />
      </v-list>
    </template>
  </v-navigation-drawer>
</template>
