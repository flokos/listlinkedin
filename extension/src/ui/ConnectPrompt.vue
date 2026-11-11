<script setup lang="ts">
// "Connect this browser": shown by the popup and the welcome page while no account is
// connected. Connecting happens on the site (src/lib/connect.ts); this only starts it. If the
// browser hasn't granted the extension the site, it asks for that first.
import { onMounted, ref } from 'vue'

import { hasSiteAccess, requestSiteAccess } from '../lib/access'
import { SITE } from '../lib/config'
import { startConnect } from '../lib/connect'
import NoticeBox from './NoticeBox.vue'

defineProps<{
  /** Why the browser is no longer connected, when it was. */
  ended?: boolean
}>()
const emit = defineEmits<{ started: [] }>()

const host = new URL(SITE).host
const access = ref<boolean>()
const busy = ref(false)
const error = ref('')

onMounted(async () => {
  access.value = await hasSiteAccess().catch(() => true)
})

async function allow() {
  error.value = ''
  access.value = await requestSiteAccess().catch(() => false)
  if (!access.value) error.value = `Without access to ${host} the extension can't save anything.`
}

async function connect() {
  busy.value = true
  error.value = ''
  try {
    await startConnect()
    emit('started')
  } catch {
    error.value = "Couldn't open listlinkedin. Try again."
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="ll-connect">
    <NoticeBox v-if="ended" tone="warning">
      This browser was disconnected from your account. Connect it again to keep saving.
    </NoticeBox>
    <NoticeBox v-if="error" tone="error">{{ error }}</NoticeBox>

    <template v-if="access === false">
      <p>
        The extension needs your permission to talk to <strong>{{ host }}</strong
        >, where your lists are. It asks for no other site.
      </p>
      <div><button type="button" class="ll-button" @click="allow">Allow access</button></div>
    </template>
    <template v-else>
      <p>
        Connect this browser to your listlinkedin account once, and save pages to your lists from
        any tab.
      </p>
      <p class="ll-muted">
        You approve it on {{ host }}. Your password is never typed into the extension.
      </p>
      <div>
        <button
          type="button"
          class="ll-button"
          :disabled="busy || access === undefined"
          @click="connect"
        >
          Connect this browser
        </button>
      </div>
    </template>
  </section>
</template>

<style scoped>
.ll-connect {
  display: grid;
  gap: 12px;
}
</style>
