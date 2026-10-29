<script setup lang="ts">
import {
  mdiAccountCircleOutline,
  mdiDotsVertical,
  mdiLogin,
  mdiLogout,
  mdiMenu,
  mdiOpenInNew,
  mdiPlus,
} from '@mdi/js'
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useDisplay } from 'vuetify'

import { useOwnedLists } from '../composables/useOwnedLists'
import { useSession } from '../composables/useSession'
import { useSignOut } from '../composables/useSignOut'
import { externalNav, shownNav, signInRoute, type NavItem } from '../navigation'
import AppLogo from './AppLogo.vue'
import ThemeMenu from './ThemeMenu.vue'

defineEmits<{ 'toggle-drawer': [] }>()

const route = useRoute()
const { mdAndUp } = useDisplay()
const { count } = useOwnedLists()
const { user, ready } = useSession()
const signOut = useSignOut()
const isActive = (item: NavItem) => item.match.includes(String(route.name))
const signIn = computed(() => signInRoute(route))
const isDev = import.meta.env.DEV
</script>

<template>
  <v-app-bar flat border="b" color="surface" height="64">
    <div class="ll-header d-flex align-center w-100 px-2 px-sm-4 ga-1">
      <v-btn
        v-if="!mdAndUp"
        :icon="mdiMenu"
        variant="text"
        aria-label="Open menu"
        @click="$emit('toggle-drawer')"
      />
      <router-link
        to="/"
        class="ll-header__brand text-decoration-none mr-4"
        aria-label="listlinkedin home"
      >
        <AppLogo :size="30" />
      </router-link>

      <nav v-if="mdAndUp" aria-label="Main" class="d-flex ga-1">
        <v-btn
          v-for="item in shownNav"
          :key="item.label"
          :to="item.to"
          variant="text"
          :color="isActive(item) ? 'primary' : undefined"
          :aria-current="isActive(item) ? 'page' : undefined"
        >
          {{ item.label }}
          <v-badge
            v-if="item.badge && count"
            :content="count"
            inline
            color="primary-container"
            class="ml-1"
          />
        </v-btn>
      </nav>

      <v-spacer />

      <v-btn
        v-if="mdAndUp"
        :to="{ name: 'home', hash: '#create' }"
        :active="false"
        color="primary"
        :prepend-icon="mdiPlus"
        class="mr-1"
      >
        New list
      </v-btn>
      <v-btn
        v-else
        :to="{ name: 'home', hash: '#create' }"
        :active="false"
        :icon="mdiPlus"
        color="primary"
        variant="tonal"
        size="small"
        aria-label="New list"
        class="mr-1"
      />
      <ThemeMenu />
      <v-menu v-if="user" location="bottom end">
        <template #activator="{ props }">
          <v-btn
            v-bind="props"
            :icon="mdiAccountCircleOutline"
            variant="text"
            aria-label="Account menu"
          />
        </template>
        <v-list role="menu" density="compact" nav min-width="240">
          <v-list-subheader class="ll-account-name">
            {{ user.display_name || user.email }}
          </v-list-subheader>
          <v-list-item
            role="menuitem"
            :to="{ name: 'account' }"
            :prepend-icon="mdiAccountCircleOutline"
            title="Your account"
          />
          <v-list-item
            role="menuitem"
            :prepend-icon="mdiLogout"
            title="Sign out"
            @click="signOut"
          />
        </v-list>
      </v-menu>
      <template v-else-if="ready">
        <v-btn v-if="mdAndUp" :to="signIn" variant="text">Sign in</v-btn>
        <v-btn v-else :to="signIn" :icon="mdiLogin" variant="text" aria-label="Sign in" />
      </template>
      <v-menu>
        <template #activator="{ props }">
          <v-btn v-bind="props" :icon="mdiDotsVertical" variant="text" aria-label="More" />
        </template>
        <v-list role="menu" density="compact" nav>
          <v-list-item
            v-for="link in externalNav"
            :key="link.label"
            role="menuitem"
            :href="link.href"
            target="_blank"
            rel="noopener noreferrer"
            :title="link.label"
            :append-icon="mdiOpenInNew"
          />
          <v-list-item
            v-if="isDev"
            role="menuitem"
            :to="{ name: 'design' }"
            title="Design system"
          />
        </v-list>
      </v-menu>
    </div>
  </v-app-bar>
</template>

<style scoped>
.ll-header {
  max-width: 1200px;
  margin-inline: auto;
}
.ll-header__brand {
  border-radius: 8px;
}
.ll-account-name {
  overflow-wrap: anywhere;
}
</style>
