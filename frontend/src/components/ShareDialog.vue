<script setup lang="ts">
import { mdiExportVariant, mdiEyeOutline } from '@mdi/js'
import QRCode from 'qrcode'
import { computed, ref, watch } from 'vue'

import type { MemberKind, Visibility } from '../api'

import { useShare } from '../composables/useShare'
import { mauve, violet } from '../design/tokens'
import CopyField from './CopyField.vue'
import MembersPanel from './MembersPanel.vue'

const open = defineModel<boolean>({ required: true })
const props = withDefaults(
  defineProps<{
    /** What is shared: a list (the default) or a group. */
    kind?: MemberKind
    title: string
    url: string
    visibility: Visibility
    /** The owner may change who can see the list. */
    canChange?: boolean
    /** Making a list public (and adding people) needs a verified email address. */
    emailVerified?: boolean
    /** Shows the People section (owner and editors): the list's code is needed for it. */
    people?: { code: string; ownerName: string | null; youAreOwner: boolean; canManage: boolean }
  }>(),
  { kind: 'list', people: undefined },
)
const emit = defineEmits<{ 'change-visibility': [visibility: Visibility] }>()

const options: { value: Visibility; label: string; hint: string }[] = [
  {
    value: 'private',
    label: 'Only people you add',
    hint: 'Nobody else can open it, even with the link.',
  },
  { value: 'unlisted', label: 'Anyone with the link', hint: "It isn't listed anywhere." },
  { value: 'public', label: 'Public', hint: 'Anyone can find it.' },
]
const describe = computed<Record<Visibility, string>>(() => ({
  private: 'Only people you add can open this link.',
  unlisted: `Anyone with this link can view the ${props.kind}, but not change it.`,
  public: `Anyone can view this ${props.kind}, but not change it.`,
}))

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
  <v-dialog v-model="open" max-width="480" :aria-label="`Share this ${kind}`">
    <v-card class="pa-2">
      <v-card-item>
        <v-card-title class="text-title-large">Share this {{ kind }}</v-card-title>
        <v-card-subtitle class="text-wrap">{{ title }}</v-card-subtitle>
      </v-card-item>
      <v-card-text class="pt-4">
        <v-radio-group
          v-if="canChange"
          :model-value="visibility"
          :label="`Who can see this ${kind}`"
          class="mb-2"
          hide-details
          @update:model-value="(value) => value && emit('change-visibility', value as Visibility)"
        >
          <v-radio
            v-for="option in options"
            :key="option.value"
            :value="option.value"
            :disabled="option.value === 'public' && !emailVerified && visibility !== 'public'"
          >
            <template #label>
              <span>
                {{ option.label }}
                <span class="d-block text-body-small text-medium-emphasis">
                  {{
                    option.value === 'public' && !emailVerified
                      ? `Verify your email address on your account page to publish ${kind}s.`
                      : option.hint
                  }}
                </span>
              </span>
            </template>
          </v-radio>
        </v-radio-group>
        <CopyField label="Share link" :value="url" what="Share link" />
        <div class="ll-qr mx-auto my-4">
          <img v-if="qr" :src="qr" :alt="`QR code for ${url}`" width="220" height="220" />
          <v-skeleton-loader v-else type="image" width="220" height="220" />
        </div>
        <p class="d-flex align-center ga-2 text-body-small text-medium-emphasis justify-center">
          <v-icon :icon="mdiEyeOutline" size="18" />
          {{ describe[visibility] }}
        </p>
        <p v-if="kind === 'group'" class="text-body-small text-medium-emphasis text-center mt-2">
          Each list in the group is shown only to people who may see that list.
        </p>
        <MembersPanel
          v-if="people"
          :code="people.code"
          :owner-name="people.ownerName"
          :you-are-owner="people.youAreOwner"
          :kind="kind"
          :can-manage="people.canManage"
          :email-verified="Boolean(emailVerified)"
        />
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
