<script setup lang="ts">
// The add form. On phones it starts closed once the list has links, so the links come first
// and "Add a link" opens it; on larger screens it starts open and can be closed
// (docs/v2/11-UI-UX-MIGRATION.md#list-page).
import { mdiChevronDown, mdiChevronUp, mdiLinkVariantPlus } from '@mdi/js'
import { nextTick, ref } from 'vue'
import { useDisplay } from 'vuetify'

import { LIMITS, type LinkInput } from '../api'
import LinkForm from './LinkForm.vue'
import LinkLimitMeter from './LinkLimitMeter.vue'

const props = defineProps<{ count: number; submit: (input: LinkInput) => Promise<unknown> }>()
const { xs } = useDisplay()

const open = ref(!(xs.value && props.count > 0))
const form = ref<InstanceType<typeof LinkForm>>()

async function toggle() {
  open.value = !open.value
  if (open.value) {
    await nextTick()
    form.value?.focus()
  }
}
</script>

<template>
  <v-card class="pa-4 pa-sm-5 mb-8 ll-add-card" color="surface-container">
    <div class="d-flex flex-wrap align-center justify-space-between ga-4" :class="{ 'mb-4': open }">
      <h2 class="text-title-large">
        <button
          type="button"
          class="ll-add-card__toggle d-flex align-center ga-2"
          :aria-expanded="open"
          aria-controls="add-link-form"
          @click="toggle"
        >
          <v-icon :icon="mdiLinkVariantPlus" color="primary" /> Add a link
          <v-icon :icon="open ? mdiChevronUp : mdiChevronDown" size="22" />
        </button>
      </h2>
      <LinkLimitMeter :count="props.count" />
    </div>
    <v-expand-transition>
      <div v-show="open" id="add-link-form">
        <v-alert
          v-if="props.count >= LIMITS.linksPerList"
          type="info"
          density="compact"
          class="mb-3"
          text="This list has reached its limit of 100 links. Delete one to add another."
        />
        <LinkForm
          ref="form"
          mode="add"
          :disabled="props.count >= LIMITS.linksPerList"
          :submit="submit"
        />
      </div>
    </v-expand-transition>
  </v-card>
</template>

<style scoped>
.ll-add-card {
  border-color: rgba(var(--v-theme-primary), 0.25) !important;
}
.ll-add-card__toggle {
  font: inherit;
  color: inherit;
  background: none;
  border: 0;
  padding: 0;
  cursor: pointer;
  border-radius: 8px;
}
.ll-add-card__toggle:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 4px;
}
</style>
