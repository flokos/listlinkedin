<script setup lang="ts">
// Report a list or group to the people who run the site (task 9.0): what's wrong with it,
// and optionally more. The owner isn't told; the operator decides what to do.
import { mdiFlagOutline } from '@mdi/js'
import { computed, ref, watch } from 'vue'

import { LIMITS, type ReportInput, type ReportReason } from '../api'
import { formErrors, noErrors } from '../utils/forms'

const open = defineModel<boolean>({ required: true })
const props = defineProps<{
  kind: 'list' | 'group'
  title: string
  /** Sends the report; throws to show the error. */
  send: (input: ReportInput) => Promise<unknown>
}>()
const emit = defineEmits<{ sent: [] }>()

const REASONS: { value: ReportReason; label: string; hint: string }[] = [
  {
    value: 'phishing',
    label: 'Phishing or malware',
    hint: 'It tries to steal passwords or install harmful software.',
  },
  { value: 'spam', label: 'Spam', hint: 'Unwanted ads or misleading links.' },
  { value: 'illegal', label: 'Illegal content', hint: 'Something that breaks the law.' },
  { value: 'other', label: 'Something else', hint: 'Tell us below what is wrong.' },
]

const FIELDS = ['reason', 'details'] as const
const reason = ref<ReportReason | null>(null)
const details = ref('')
const errors = ref(noErrors(FIELDS))
const busy = ref(false)
const card = ref<{ $el: HTMLElement }>()
const detailsLabel = computed(() =>
  reason.value === 'other' ? 'What is wrong?' : 'Details (optional)',
)

watch(open, (isOpen) => {
  if (!isOpen) return
  reason.value = null
  details.value = ''
  errors.value = noErrors(FIELDS)
})

function focusFirstReason() {
  card.value?.$el.querySelector<HTMLInputElement>('input[type="radio"]')?.focus()
}

async function submit() {
  errors.value = noErrors(FIELDS)
  if (!reason.value) {
    errors.value.fields.reason = ['Choose what is wrong.']
    return
  }
  if (reason.value === 'other' && !details.value.trim()) {
    errors.value.fields.details = ['Tell us what is wrong.']
    return
  }
  busy.value = true
  try {
    await props.send({ reason: reason.value, details: details.value.trim() })
    open.value = false
    emit('sent')
  } catch (error) {
    errors.value = formErrors(error, FIELDS)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <v-dialog
    v-model="open"
    max-width="520"
    scrollable
    :aria-label="`Report this ${kind}`"
    @after-enter="focusFirstReason"
  >
    <v-card ref="card" class="pa-2">
      <v-card-item>
        <v-card-title class="text-title-large">Report this {{ kind }}</v-card-title>
        <v-card-subtitle class="text-wrap">{{ title }}</v-card-subtitle>
      </v-card-item>
      <v-form @submit.prevent="submit">
        <v-card-text>
          <p class="text-body-medium text-medium-emphasis mb-4">
            Your report goes to the people who run listlinkedin, not to the {{ kind }}'s owner.
          </p>
          <v-radio-group
            v-model="reason"
            :label="`What's wrong with this ${kind}?`"
            :error-messages="errors.fields.reason"
            @update:model-value="errors.fields.reason = []"
          >
            <v-radio v-for="option in REASONS" :key="option.value" :value="option.value">
              <template #label>
                <span>
                  {{ option.label }}
                  <span class="d-block text-body-small text-medium-emphasis">{{
                    option.hint
                  }}</span>
                </span>
              </template>
            </v-radio>
          </v-radio-group>
          <v-textarea
            v-model="details"
            :label="detailsLabel"
            rows="3"
            auto-grow
            counter
            :maxlength="LIMITS.reportDetailsLength"
            :error-messages="errors.fields.details"
            class="mt-2"
            @update:model-value="errors.fields.details = []"
          />
          <v-alert
            v-if="errors.form"
            type="error"
            density="compact"
            class="mt-3"
            :text="errors.form"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="open = false">Cancel</v-btn>
          <v-btn
            type="submit"
            color="primary"
            variant="flat"
            :prepend-icon="mdiFlagOutline"
            :loading="busy"
            >Send report</v-btn
          >
        </v-card-actions>
      </v-form>
    </v-card>
  </v-dialog>
</template>
