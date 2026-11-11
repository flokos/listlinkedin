<script setup lang="ts">
// Opened once, right after the extension is installed: what it does, and "Connect this
// browser". It stays open while the user approves on the site, and then says what to do next.
import { onBeforeUnmount, onMounted, ref } from 'vue'

import { type Connection, getConnection, onConnectionChange } from '../../lib/storage'
import BrandMark from '../../ui/BrandMark.vue'
import ConnectPrompt from '../../ui/ConnectPrompt.vue'
import NoticeBox from '../../ui/NoticeBox.vue'

const connection = ref<Connection | null>()
let stop = () => {}

onMounted(async () => {
  connection.value = await getConnection()
  stop = onConnectionChange((next) => (connection.value = next))
})
onBeforeUnmount(() => stop())
</script>

<template>
  <main class="ll-page">
    <BrandMark :size="32" />
    <h1>Save pages to your lists from any tab</h1>
    <p class="ll-muted">
      The listlinkedin extension adds a button to your browser's toolbar. Click it on a page, pick
      one of your lists, and the page is saved there.
    </p>

    <section v-if="connection" class="ll-card welcome__card">
      <NoticeBox tone="success">
        This browser is connected to <strong>{{ connection.email }}</strong
        >.
      </NoticeBox>
      <h2>What now</h2>
      <ol class="welcome__steps">
        <li>Open a page you want to keep.</li>
        <li>Click the listlinkedin button in the toolbar. Pin it there if it is hidden.</li>
        <li>Choose a list and save.</li>
      </ol>
      <p class="ll-muted">You can close this tab.</p>
    </section>
    <section v-else-if="connection === null" class="ll-card welcome__card">
      <h2>First, connect this browser</h2>
      <ConnectPrompt />
    </section>
  </main>
</template>

<style scoped>
.welcome__card {
  display: grid;
  gap: 12px;
}
.welcome__steps {
  display: grid;
  gap: 4px;
  margin: 0;
  padding-left: 20px;
}
</style>
