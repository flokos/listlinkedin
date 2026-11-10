<script setup lang="ts">
// The toolbar popup. Not connected: "Connect this browser". Connected: save this page.
import { onBeforeUnmount, onMounted, ref } from 'vue'

import { ext } from '../lib/ext'
import { type Connection, getConnection, onConnectionChange } from '../lib/storage'
import BrandMark from '../ui/BrandMark.vue'
import ConnectPrompt from '../ui/ConnectPrompt.vue'
import SavePanel from './SavePanel.vue'

const connection = ref<Connection | null>()
/** The connection ended while the popup was open. */
const ended = ref(false)
let stop = () => {}

onMounted(async () => {
  connection.value = await getConnection()
  stop = onConnectionChange((next) => {
    // Connected a moment ago and now not: the site ended it while the popup was open (the
    // account is forgotten before the request that found out has finished failing).
    ended.value = Boolean(connection.value) && !next
    connection.value = next
  })
})
onBeforeUnmount(() => stop())

function disconnected() {
  ended.value = true
  connection.value = null
}

const options = () => ext().runtime.openOptionsPage()
// The Connect page opens in a new tab; a popup would close by itself, a page stays.
const started = () => window.close()
</script>

<template>
  <main class="popup">
    <header class="popup__header">
      <BrandMark />
      <button type="button" class="ll-button ll-button--text" @click="options">Options</button>
    </header>
    <h1 class="ll-visually-hidden">Save to listlinkedin</h1>
    <p v-if="connection === undefined" class="ll-muted" aria-busy="true">Loading…</p>
    <ConnectPrompt v-else-if="connection === null" :ended="ended" @started="started" />
    <template v-else>
      <SavePanel @disconnected="disconnected" />
      <p class="popup__account ll-muted">{{ connection.email }}</p>
    </template>
  </main>
</template>

<style scoped>
.popup {
  display: grid;
  gap: 12px;
  width: 360px;
  max-width: 100%;
  padding: 14px 16px 12px;
}
.popup__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.popup__account {
  overflow: hidden;
  padding-top: 8px;
  border-top: 1px solid var(--ll-outline-variant);
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}
</style>
