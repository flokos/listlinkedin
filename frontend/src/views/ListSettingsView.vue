<script setup lang="ts">
// A list's settings (/l/:code/settings, task 8.3). Each section saves on its own and shows only
// to whoever may change it; the server checks every change again. Who can see the list,
// copies and people stay in the Share dialog, which this page opens.
import {
  mdiAlertCircleOutline,
  mdiArrowLeft,
  mdiLinkOff,
  mdiLockOutline,
  mdiRefresh,
  mdiShareVariant,
} from '@mdi/js'
import { computed, ref, toRef, watch } from 'vue'
import { useRouter } from 'vue-router'

import { ApiError, errorMessage, LIMITS } from '../api'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import ImageUploadField from '../components/ImageUploadField.vue'
import StatePanel from '../components/StatePanel.vue'
import TagsField from '../components/TagsField.vue'
import { useListPage } from '../composables/useListPage'
import { useNotify } from '../composables/useNotify'
import { formErrors, noErrors } from '../utils/forms'
import { endOfDay, localDate } from '../utils/time'

const props = defineProps<{ code: string }>()
const router = useRouter()
const notify = useNotify()
const page = useListPage(toRef(props, 'code'))
const { list, status } = page

const canAbout = computed(() => page.can('edit'))
const canAny = computed(() =>
  ['edit', 'upload', 'tags', 'settings', 'delete'].some((p) => page.can(p)),
)

watch(
  () => list.value?.title,
  (title) => {
    if (title) document.title = `Settings: ${title} · listlinkedin`
  },
)

// Name and description: content, so a version is recorded and the save is based on the
// version on screen (If-Match). A list changed meanwhile is reloaded, and the form says so.
const ABOUT = ['title', 'description'] as const
const title = ref('')
const description = ref('')
const aboutErrors = ref(noErrors(ABOUT))
const aboutBusy = ref(false)
const aboutChanged = computed(
  () =>
    list.value !== undefined &&
    (title.value.trim() !== list.value.title ||
      description.value.trim() !== list.value.description),
)

// Tags: not content, no version.
const tags = ref<string[]>([])
const tagErrors = ref(noErrors(['tags'] as const))
const tagsBusy = ref(false)
const tagsChanged = computed(
  () => list.value !== undefined && tags.value.join() !== list.value.tags.join(),
)

// Expiry: the owner's. A date means the list is deleted at the end of that day.
const expires = ref<'never' | 'on'>('never')
const expiryDate = ref('')
const expiryErrors = ref(noErrors(['expires_at'] as const))
const expiryBusy = ref(false)
const tomorrow = computed(() => {
  const date = new Date()
  date.setDate(date.getDate() + 1)
  return localDate(date.toISOString())
})

function fillAbout() {
  title.value = list.value?.title ?? ''
  description.value = list.value?.description ?? ''
}
function fill() {
  if (!list.value) return
  fillAbout()
  tags.value = [...list.value.tags]
  expires.value = list.value.expires_at ? 'on' : 'never'
  expiryDate.value = list.value.expires_at ? localDate(list.value.expires_at) : ''
}
watch(() => list.value?.code, fill, { immediate: true })
// New content (this page's save, or someone else's found by a 412) shows in the form. Not
// keyed on head_revision: the new number arrives (ETag) before the new content.
watch(() => [list.value?.title, list.value?.description], fillAbout)

async function saveAbout() {
  aboutErrors.value = noErrors(ABOUT)
  const name = title.value.trim()
  if (!name) {
    aboutErrors.value.fields.title = ['A list needs a name.']
    return
  }
  aboutBusy.value = true
  try {
    await page.change({ title: name, description: description.value.trim() })
    notify.success('Name and description saved')
  } catch (error) {
    if (error instanceof ApiError && error.status === 412) {
      aboutErrors.value.form =
        'Someone changed this list while you were editing. It has been reloaded: check the name and description, then save again.'
    } else aboutErrors.value = formErrors(error, ABOUT)
  } finally {
    aboutBusy.value = false
  }
}

async function saveTags() {
  tagErrors.value = noErrors(['tags'] as const)
  tagsBusy.value = true
  try {
    await page.change({ tags: tags.value })
    tags.value = [...(list.value?.tags ?? [])]
    notify.success('Tags saved')
  } catch (error) {
    tagErrors.value = formErrors(error, ['tags'] as const)
  } finally {
    tagsBusy.value = false
  }
}

async function saveExpiry() {
  expiryErrors.value = noErrors(['expires_at'] as const)
  if (expires.value === 'on' && !expiryDate.value) {
    expiryErrors.value.fields.expires_at = ['Choose a date.']
    return
  }
  expiryBusy.value = true
  try {
    await page.change({ expires_at: expires.value === 'on' ? endOfDay(expiryDate.value) : null })
    notify.success(expires.value === 'on' ? 'Expiry date saved' : 'This list no longer expires')
  } catch (error) {
    expiryErrors.value = formErrors(error, ['expires_at'] as const)
  } finally {
    expiryBusy.value = false
  }
}

async function setImage(file: File | null) {
  await page.setImage(file)
  notify.success(file ? 'Image updated' : 'Image removed')
}

const deleteOpen = ref(false)
async function confirmDelete() {
  try {
    await page.removeList()
  } catch (error) {
    notify.error(errorMessage(error))
    throw error
  }
  notify.success('List deleted')
  await router.replace({ name: 'saved-lists' })
}

const visibilityLabel = {
  private: 'Only people you add can open it.',
  unlisted: 'Anyone with the link can open it.',
  public: 'Public: anyone can find it in Explore.',
} as const
</script>

<template>
  <div class="ll-content ll-reading py-6 py-md-10">
    <v-btn
      :prepend-icon="mdiArrowLeft"
      variant="text"
      class="mb-4 ml-n3"
      :to="{ name: 'list', params: { code } }"
    >
      {{ list?.title ?? 'Back to the list' }}
    </v-btn>

    <div v-if="status === 'loading'" aria-busy="true" aria-label="Loading settings">
      <v-skeleton-loader type="heading" class="mb-6" max-width="320" />
      <v-skeleton-loader v-for="n in 3" :key="n" type="article" />
    </div>
    <StatePanel
      v-else-if="status === 'not-found'"
      as="h1"
      :icon="mdiLinkOff"
      title="This list doesn't exist"
      text="It may have been deleted, the link is mistyped, or it isn't shared with you."
    />
    <StatePanel
      v-else-if="status === 'expired'"
      as="h1"
      tone="warning"
      :icon="mdiAlertCircleOutline"
      title="This list has expired"
    />
    <StatePanel
      v-else-if="status === 'error'"
      as="h1"
      tone="error"
      :icon="mdiAlertCircleOutline"
      title="Couldn't load this list"
      :text="errorMessage(page.loadError.value)"
    >
      <template #actions>
        <v-btn color="primary" :prepend-icon="mdiRefresh" @click="page.load()">Try again</v-btn>
      </template>
    </StatePanel>

    <template v-else-if="list">
      <StatePanel
        v-if="!canAny"
        as="h1"
        :icon="mdiLockOutline"
        title="You can't change this list's settings"
        text="Only its owner and the people who can edit it can."
      >
        <template #actions>
          <v-btn color="primary" :to="{ name: 'list', params: { code } }">Open the list</v-btn>
        </template>
      </StatePanel>

      <template v-else>
        <h1 class="text-headline-large mb-8">Settings</h1>

        <section v-if="canAbout" class="ll-settings__section" aria-labelledby="about-heading">
          <h2 id="about-heading" class="text-title-large mb-4">Name and description</h2>
          <v-form @submit.prevent="saveAbout">
            <v-text-field
              v-model="title"
              label="Name"
              :maxlength="LIMITS.titleLength"
              :error-messages="aboutErrors.fields.title"
              @update:model-value="aboutErrors.fields.title = []"
            />
            <v-textarea
              v-model="description"
              label="Description (optional)"
              hint="Shown under the name, and searched in Explore when the list is public."
              persistent-hint
              rows="3"
              auto-grow
              counter
              :maxlength="LIMITS.descriptionLength"
              :error-messages="aboutErrors.fields.description"
              class="mt-2"
            />
            <v-alert
              v-if="aboutErrors.form"
              type="error"
              density="compact"
              class="mt-3"
              :text="aboutErrors.form"
            />
            <div class="d-flex justify-end mt-3">
              <v-btn type="submit" color="primary" :loading="aboutBusy" :disabled="!aboutChanged"
                >Save name and description</v-btn
              >
            </div>
          </v-form>
        </section>

        <section
          v-if="page.can('upload')"
          class="ll-settings__section"
          aria-labelledby="image-heading"
        >
          <h2 id="image-heading" class="text-title-large mb-2">Image</h2>
          <p class="text-body-medium text-medium-emphasis mb-4">
            Shown next to the name, and on the list's card in Explore.
          </p>
          <ImageUploadField label="List image" :image-url="list.image_url" :save="setImage" />
        </section>

        <section
          v-if="page.can('tags')"
          class="ll-settings__section"
          aria-labelledby="tags-heading"
        >
          <h2 id="tags-heading" class="text-title-large mb-4">Tags</h2>
          <v-form @submit.prevent="saveTags">
            <TagsField v-model="tags" :error-messages="tagErrors.fields.tags" />
            <v-alert
              v-if="tagErrors.form"
              type="error"
              density="compact"
              class="mt-3"
              :text="tagErrors.form"
            />
            <div class="d-flex justify-end mt-3">
              <v-btn type="submit" color="primary" :loading="tagsBusy" :disabled="!tagsChanged"
                >Save tags</v-btn
              >
            </div>
          </v-form>
        </section>

        <template v-if="page.can('settings')">
          <section class="ll-settings__section" aria-labelledby="sharing-heading">
            <h2 id="sharing-heading" class="text-title-large mb-2">Sharing</h2>
            <p class="text-body-medium mb-4">{{ visibilityLabel[list.visibility] }}</p>
            <v-btn
              variant="tonal"
              color="primary"
              :prepend-icon="mdiShareVariant"
              :to="{ name: 'list', params: { code }, query: { dialog: 'share' } }"
              >Who can see it, copies and people</v-btn
            >
          </section>

          <section class="ll-settings__section" aria-labelledby="expiry-heading">
            <h2 id="expiry-heading" class="text-title-large mb-2">Expiry</h2>
            <v-form @submit.prevent="saveExpiry">
              <v-radio-group
                v-model="expires"
                aria-labelledby="expiry-heading"
                hide-details
                @update:model-value="expiryErrors = noErrors(['expires_at'])"
              >
                <v-radio value="never" label="Keep it permanently" />
                <v-radio value="on" label="Delete it automatically on a date" />
              </v-radio-group>
              <v-text-field
                v-if="expires === 'on'"
                v-model="expiryDate"
                type="date"
                label="Delete at the end of"
                :min="tomorrow"
                :error-messages="expiryErrors.fields.expires_at"
                class="mt-3 ll-settings__date"
              />
              <v-alert
                v-if="expiryErrors.form"
                type="error"
                density="compact"
                class="mt-3"
                :text="expiryErrors.form"
              />
              <div class="d-flex justify-end mt-3">
                <v-btn type="submit" color="primary" :loading="expiryBusy">Save expiry</v-btn>
              </div>
            </v-form>
          </section>
        </template>

        <section
          v-if="page.can('delete')"
          class="ll-settings__section ll-settings__danger"
          aria-labelledby="delete-heading"
        >
          <h2 id="delete-heading" class="text-title-large mb-2">Delete this list</h2>
          <p class="text-body-medium text-medium-emphasis mb-4">
            The list, its links and their short links go away for everyone. This can't be undone.
          </p>
          <v-btn color="error" variant="flat" @click="deleteOpen = true">Delete list…</v-btn>
        </section>

        <ConfirmDialog
          v-model="deleteOpen"
          title="Delete this list?"
          text="The list, all its links and their short links will be removed for everyone. This can't be undone."
          action="Delete list"
          :confirm-text="list.title"
          :on-confirm="confirmDelete"
        />
      </template>
    </template>
  </div>
</template>

<style scoped>
.ll-settings__section {
  padding: 24px 0;
  border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.ll-settings__danger h2 {
  color: rgb(var(--v-theme-error));
}
.ll-settings__date {
  max-width: 260px;
}
</style>
