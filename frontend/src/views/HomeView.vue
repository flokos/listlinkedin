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

import type { CreatedList } from '../api'
import CreateListForm from '../components/CreateListForm.vue'
import ExpiryChip from '../components/ExpiryChip.vue'
import { useOwnedLists } from '../composables/useOwnedLists'
import { usePendingReveal } from '../composables/usePendingReveal'

const route = useRoute()
const router = useRouter()
const owned = useOwnedLists()
const pending = usePendingReveal()

function onCreated(list: CreatedList) {
  owned.save({
    code: list.public_code,
    token: list.owner_token,
    title: list.title,
    expiresAt: list.expires_at,
  })
  pending.set(list.public_code, list.owner_token)
  router.push({ name: 'list', params: { code: list.public_code } })
}

const steps = [
  {
    icon: mdiViewListOutline,
    title: 'Create a list',
    text: 'Give it a name. No account, no email, nothing to install.',
  },
  {
    icon: mdiLinkVariantPlus,
    title: 'Add your links',
    text: 'Paste up to 100 links. Each one gets its own short link.',
  },
  {
    icon: mdiShareVariantOutline,
    title: 'Share it',
    text: 'Send the view link or QR code to your team. Only you can edit.',
  },
]

const promises = [
  { icon: mdiAccountOffOutline, text: 'No sign-up' },
  { icon: mdiShieldKeyOutline, text: 'Private edit link' },
  { icon: mdiTimerSandEmpty, text: 'Gone after 30 days' },
]
</script>

<template>
  <div>
    <section class="ll-hero ll-hero-wash mx-n4 px-4">
      <div class="ll-content py-12 py-md-16">
        <p class="text-label-large text-primary mb-3">Temporary link lists for teams</p>
        <h1 class="text-display-small ll-hero__title mb-4">
          Collect links. Share one URL.
          <span class="ll-hero__accent">Done in seconds.</span>
        </h1>
        <p class="text-body-large text-medium-emphasis ll-reading mb-8">
          Make a list of interesting links for your next team bonding, share it with a single link,
          and let it disappear on its own after 30 days.
        </p>
        <div id="create" class="ll-hero__form">
          <CreateListForm :autofocus="route.hash === '#create'" @created="onCreated" />
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
        <h2 id="recent-heading" class="text-headline-small">Your lists on this device</h2>
        <v-btn
          :to="{ name: 'my-lists' }"
          variant="text"
          color="primary"
          :append-icon="mdiArrowRight"
        >
          All lists
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
            Anyone you give the share link to. List addresses are long random codes that can't be
            guessed, and search engines are asked not to index them.
          </v-expansion-panel-text>
        </v-expansion-panel>
        <v-expansion-panel title="How do I edit it later, or from another device?">
          <v-expansion-panel-text>
            When you create a list you get a private edit link. This browser remembers it, and
            opening it anywhere else unlocks editing there too. Keep it safe: there's no account to
            recover it from.
          </v-expansion-panel-text>
        </v-expansion-panel>
        <v-expansion-panel title="What happens after 30 days?">
          <v-expansion-panel-text>
            The list and all its short links stop working, and the data is deleted within a day. You
            can delete a list sooner from its menu.
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
