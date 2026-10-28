<script setup lang="ts">
import { mdiExportVariant, mdiEyeOutline } from '@mdi/js'
import QRCode from 'qrcode'
import { ref, watch } from 'vue'

import { useShare } from '../composables/useShare'
import { mauve, violet } from '../design/tokens'
import CopyField from './CopyField.vue'

const open = defineModel<boolean>({ required: true })
const props = defineProps<{ title: string; url: string }>()

const qr = ref<string>()
const { canShare, share } = useShare()

// Generated in the browser: the link never goes to a third-party QR service.
watch(
  [open, () => props.url],
  async ([isOpen]) => {
    if (!isOpen || qr.value) return
    qr.value = await QRCode.toDataURL(props.url, {
      margin: 1,
      width: 480,
      errorCorrectionLevel: 'M',
      color: { dark: violet[950], light: mauve[0] },
    })
  },
  { immediate: true },
)
</script>

<template>
  <v-dialog v-model="open" max-width="480" aria-label="Share this list">
    <v-card class="pa-2">
      <v-card-item>
        <v-card-title class="text-title-large">Share this list</v-card-title>
        <v-card-subtitle class="text-wrap">{{ title }}</v-card-subtitle>
      </v-card-item>
      <v-card-text class="pt-4">
        <CopyField label="Share link" :value="url" what="Share link" />
        <div class="ll-qr mx-auto my-4">
          <img v-if="qr" :src="qr" :alt="`QR code for ${url}`" width="220" height="220" />
          <v-skeleton-loader v-else type="image" width="220" height="220" />
        </div>
        <p class="d-flex align-center ga-2 text-body-small text-medium-emphasis justify-center">
          <v-icon :icon="mdiEyeOutline" size="18" />
          Anyone with this link can view the list, but not change it.
        </p>
      </v-card-text>
      <v-card-actions>
        <v-btn
          v-if="canShare"
          :prepend-icon="mdiExportVariant"
          variant="tonal"
          color="primary"
          @click="share({ title, text: title, url })"
        >
          Share…
        </v-btn>
        <v-spacer />
        <v-btn variant="text" @click="open = false">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.ll-qr {
  width: 236px;
  padding: 8px;
  border-radius: 16px;
  background: #fff;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.ll-qr img {
  display: block;
  width: 220px;
  height: 220px;
}
</style>
