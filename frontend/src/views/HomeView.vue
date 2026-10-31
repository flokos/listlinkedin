<script setup lang="ts">
import {
  mdiAccountOffOutline,
  mdiArrowRight,
  mdiLinkVariantPlus,
  mdiShareVariantOutline,
  mdiShieldKeyOutline,
  mdiTimerSandEmpty,
  mdiViewListOutline,
} from '@mdi/js'
import { useRoute, useRouter } from 'vue-router'

import type { ListDetail } from '../api'
import CreateListForm from '../components/CreateListForm.vue'
import ExpiryChip from '../components/ExpiryChip.vue'
import { useOwnedLists } from '../composables/useOwnedLists'
import { useSession } from '../composables/useSession'

const route = useRoute()
const router = useRouter()
const owned = useOwnedLists()
const { isSignedIn, ready } = useSession()

function onCreated(list: ListDetail) {
  router.push({ name: 'list', params: { code: list.code, slug: list.slug } })
}

const steps = [
  {
    icon: mdiViewListOutline,
    title: 'Create a list',
    text: 'Give it a name. Signing up takes a minute, with just an email address.',
  },
  {
    icon: mdiLinkVariantPlus,
    title: 'Add your links',
    text: 'Paste up to 100 links. Each one gets its own short link.',
  },
  {
    icon: mdiShareVariantOutline,
    title: 'Share it',
    text: 'Keep it private, share the link, or make it public. You decide who can edit.',
  },
]

const promises = [
  { icon: mdiAccountOffOutline, text: 'Private by default' },
  { icon: mdiShieldKeyOutline, text: 'You choose who sees it' },
  { icon: mdiTimerSandEmpty, text: 'Kept as long as you like' },
]
</script>

<template>
  <div>
    <section class="ll-hero ll-hero-wash mx-n4 px-4">
      <div class="ll-content py-12 py-md-16">
        <p class="text-label-large text-primary mb-3">Link lists for teams</p>
        <h1 class="text-display-small ll-hero__title mb-4">
          Collect links. Share one URL.
          <span class="ll-hero__accent">Done in seconds.</span>
        </h1>
        <p class="text-body-large text-medium-emphasis ll-reading mb-8">
          Make a list of interesting links for your team, then share it with a single link, keep it
          private, or publish it.
        </p>
        <div id="create" class="ll-hero__form">
          <CreateListForm
            v-if="isSignedIn"
            :autofocus="route.hash === '#create'"
            @created="onCreated"
          />
          <div v-else-if="ready" class="d-flex flex-wrap ga-3">
            <v-btn color="primary" size="x-large" :to="{ name: 'signup' }"
              >Create a free account</v-btn
            >
            <v-btn variant="tonal" color="primary" size="x-large" :to="{ name: 'signin' }"
              >Sign in</v-btn
            >
          </div>
        </div>
        <ul class="ll-promises d-flex flex-wrap ga-2 mt-6 pa-0" aria-label="Highlights">
          <li v-for="item in promises" :key="item.text">
            <v-chip :prepend-icon="item.icon" variant="outlined" size="default">{{
              item.text
            }}</v-chip>
          </li>
        </ul>
      </div>
    </section>

    <section
      v-if="owned.lists.value.length"
      class="ll-content mt-12"
      aria-labelledby="recent-heading"
    >
      <div class="d-flex align-center justify-space-between mb-4">
        <h2 id="recent-heading" class="text-headline-small">Saved on this device</h2>
        <v-btn
          :to="{ name: 'saved-lists' }"
          variant="text"
          color="primary"
          :append-icon="mdiArrowRight"
        >
          All saved lists
        </v-btn>
      </div>
      <v-row>
        <v-col
          v-for="item in owned.lists.value.slice(0, 3)"
          :key="item.code"
          cols="12"
          sm="6"
          md="4"
        >
          <v-card :to="{ name: 'list', params: { code: item.code } }" class="pa-4 h-100" hover>
            <p class="text-title-medium mb-3 text-truncate">{{ item.title || 'Untitled list' }}</p>
            <ExpiryChip v-if="item.expiresAt" :expires-at="item.expiresAt" />
          </v-card>
        </v-col>
      </v-row>
    </section>

    <section class="ll-content mt-16" aria-labelledby="how-heading">
      <h2 id="how-heading" class="text-headline-small mb-6">How it works</h2>
      <v-row>
        <v-col v-for="(step, i) in steps" :key="step.title" cols="12" md="4">
          <v-card class="pa-6 h-100" color="surface">
            <div class="d-flex align-center ga-3 mb-4">
              <div class="ll-step-icon"><v-icon :icon="step.icon" /></div>
              <span class="text-label-large text-medium-emphasis">Step {{ i + 1 }}</span>
            </div>
            <h3 class="text-title-large mb-2">{{ step.title }}</h3>
            <p class="text-body-medium text-medium-emphasis ma-0">{{ step.text }}</p>
          </v-card>
        </v-col>
      </v-row>
    </section>

    <section class="ll-content mt-16" aria-labelledby="faq-heading">
      <h2 id="faq-heading" class="text-headline-small mb-6">Good to know</h2>
      <v-expansion-panels variant="accordion" rounded="xl" class="ll-faq">
        <v-expansion-panel title="Who can see my list?">
          <v-expansion-panel-text>
            You choose: only the people you add, anyone with the share link, or everyone. List
            addresses are long random codes that can't be guessed, and search engines are asked not
            to index them.
          </v-expansion-panel-text>
        </v-expansion-panel>
        <v-expansion-panel title="How do I edit it later, or from another device?">
          <v-expansion-panel-text>
            Sign in on any device. Your lists are in your account. Have an edit link from a list
            made before accounts existed? Open it and choose "Add to my account".
          </v-expansion-panel-text>
        </v-expansion-panel>
        <v-expansion-panel title="Do lists expire?">
          <v-expansion-panel-text>
            Only if you give them an end date. Lists made before accounts existed still expire 30
            days after they were made, unless you add them to your account and keep them. You can
            delete a list any time from its menu.
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
      <p class="text-body-medium mt-6">
        <router-link :to="{ name: 'about' }" class="text-primary"
          >More about privacy and limits</router-link
        >
      </p>
    </section>
  </div>
</template>

<style scoped>
.ll-hero {
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.ll-hero__title {
  max-width: 16em;
}
.ll-hero__accent {
  background: linear-gradient(90deg, rgb(var(--v-theme-primary)), rgb(var(--v-theme-secondary)));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.ll-hero__form {
  max-width: 640px;
  scroll-margin-top: 96px;
}
.ll-promises {
  list-style: none;
}
.ll-step-icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: rgb(var(--v-theme-primary-container));
  color: rgb(var(--v-theme-on-primary-container));
}
.ll-faq :deep(.v-expansion-panel) {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
</style>
