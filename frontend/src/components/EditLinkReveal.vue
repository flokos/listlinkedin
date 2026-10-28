<script setup lang="ts">
// Shows the private edit link. After creating a list or replacing its edit link, the user
// must confirm they've saved it: the token is shown only now and can't be recovered.
import { mdiDownload, mdiShieldKeyOutline } from '@mdi/js'
import { computed, ref, watch } from 'vue'

import { buildEditLink } from '../composables/useEditLink'
import { downloadText } from '../utils/download'
import CopyField from './CopyField.vue'

const open = defineModel<boolean>({ required: true })
const props = defineProps<{
  code: string
  token: string
  title: string
  publicUrl: string
  /** created / rotated: must acknowledge. view: just showing it again. */
  mode: 'created' | 'rotated' | 'view'
}>()

const saved = ref(false)
watch(open, (value) => {
  if (value) saved.value = false
})

const editLink = computed(() => buildEditLink(props.code, props.token))
const mustAcknowledge = computed(() => props.mode !== 'view')
const heading = computed(
  () =>
    ({
      created: 'Your list is ready. Save your edit link',
      rotated: 'Here is your new edit link',
      view: 'Your edit link',
    })[props.mode],
)

function download() {
  downloadText(
    `listlinkedin-${props.code}.txt`,
    [
      `listlinkedin: ${props.title}`,
      '',
      'Share link (anyone can view):',
      props.publicUrl,
      '',
      'Edit link (PRIVATE, anyone with it can change or delete the list):',
      editLink.value,
      '',
    ].join('\n'),
  )
}
</script>

<template>
  <v-dialog v-model="open" max-width="560" :persistent="mustAcknowledge">
    <v-card class="pa-2">
      <v-card-item>
        <template #prepend>
          <div class="ll-reveal__icon mr-2"><v-icon :icon="mdiShieldKeyOutline" /></div>
        </template>
        <v-card-title class="text-title-large text-wrap">{{ heading }}</v-card-title>
      </v-card-item>

      <v-card-text class="pt-4">
        <p class="text-body-medium mb-4">
          Use this private link to edit <strong>{{ title }}</strong> from any device. It's saved in
          this browser, but there's no account, so if you lose it,
          <strong>no one can recover it</strong>.
          <template v-if="mode === 'rotated'"> Your previous edit link no longer works.</template>
        </p>

        <CopyField label="Private edit link" :value="editLink" what="Edit link" class="mb-2" />
        <v-alert type="warning" density="compact" class="mb-4 text-body-small">
          Keep it secret. Anyone with this link can change or delete the list.
        </v-alert>

        <CopyField
          v-if="mode === 'created'"
          label="Share link (view only)"
          :value="publicUrl"
          what="Share link"
          hint="Send this one to your team."
        />

        <v-checkbox
          v-if="mustAcknowledge"
          v-model="saved"
          label="I've saved my edit link somewhere safe"
          hide-details
          class="mt-2"
        />
      </v-card-text>

      <v-card-actions class="flex-wrap ga-2">
        <v-btn :prepend-icon="mdiDownload" variant="text" @click="download">Download as file</v-btn>
        <v-spacer />
        <v-btn color="primary" :disabled="mustAcknowledge && !saved" @click="open = false">
          {{ mode === 'created' ? 'Go to my list' : 'Done' }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.ll-reveal__icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: rgb(var(--v-theme-primary-container));
  color: rgb(var(--v-theme-on-primary-container));
}
</style>
