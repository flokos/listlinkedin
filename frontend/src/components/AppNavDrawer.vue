<script setup lang="ts">
import {
  mdiAccountCircleOutline,
  mdiAccountPlusOutline,
  mdiLogin,
  mdiLogout,
  mdiOpenInNew,
  mdiPlus,
} from '@mdi/js'
import { nextTick, onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'

import { useSession } from '../composables/useSession'
import { useSignOut } from '../composables/useSignOut'
import { externalNav, shownNav, signInRoute } from '../navigation'
import AppLogo from './AppLogo.vue'

const open = defineModel<boolean>({ required: true })
const route = useRoute()
const { user, ready } = useSession()
const signOut = useSignOut()
const close = () => (open.value = false)
function closeAndSignOut() {
  close()
  void signOut()
}

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
        v-for="item in shownNav"
        :key="item.label"
        :to="item.to"
        :prepend-icon="item.icon"
        :title="item.label"
        :active="item.match.includes(String(route.name))"
        color="primary"
        @click="close"
      >
      </v-list-item>
      <v-list-item
        :to="{ name: 'home', hash: '#create' }"
        :prepend-icon="mdiPlus"
        title="New list"
        base-color="primary"
        @click="close"
      />
    </v-list>

    <v-divider class="mx-4" />
    <v-list v-if="user" nav aria-label="Account">
      <v-list-item
        :to="{ name: 'account' }"
        :prepend-icon="mdiAccountCircleOutline"
        title="Your account"
        :subtitle="user.display_name || user.email"
        :active="route.name === 'account'"
        color="primary"
        @click="close"
      />
      <v-list-item :prepend-icon="mdiLogout" title="Sign out" @click="closeAndSignOut" />
    </v-list>
    <v-list v-else-if="ready" nav aria-label="Account">
      <v-list-item
        :to="signInRoute(route)"
        :prepend-icon="mdiLogin"
        title="Sign in"
        @click="close"
      />
      <v-list-item
        :to="{ name: 'signup' }"
        :prepend-icon="mdiAccountPlusOutline"
        title="Create account"
        @click="close"
      />
    </v-list>

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
