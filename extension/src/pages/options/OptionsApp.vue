<script setup lang="ts">
// The extension's options: which account this browser is connected to, and disconnecting.
import { onBeforeUnmount, onMounted, ref } from 'vue'

import { disconnect } from '../../lib/account'
import { SITE, siteUrl, VERSION } from '../../lib/config'
import { type Connection, getConnection, onConnectionChange } from '../../lib/storage'
import BrandMark from '../../ui/BrandMark.vue'
import ConnectPrompt from '../../ui/ConnectPrompt.vue'

const connection = ref<Connection | null>()
const confirming = ref(false)
const busy = ref(false)
const host = new URL(SITE).host
let stop = () => {}

onMounted(async () => {
  connection.value = await getConnection()
  stop = onConnectionChange((next) => (connection.value = next))
})
onBeforeUnmount(() => stop())

async function leave() {
  busy.value = true
  await disconnect()
  busy.value = false
  confirming.value = false
}
</script>

<template>
  <main class="ll-page">
    <BrandMark :size="32" />
    <h1>Options</h1>

    <section class="ll-card options__card" aria-labelledby="account-heading">
      <h2 id="account-heading">Account</h2>
      <template v-if="connection">
        <p>
          This browser is connected to <strong>{{ connection.email }}</strong> as “{{
            connection.name
          }}”.
        </p>
        <div v-if="confirming" class="options__confirm" role="group" aria-label="Disconnect">
          <p>
            The extension will be signed out here. Your lists stay as they are, and you can connect
            again at any time.
          </p>
          <div class="ll-row">
            <button
              type="button"
              class="ll-button ll-button--danger"
              :disabled="busy"
              @click="leave"
            >
              Disconnect this browser
            </button>
            <button
              type="button"
              class="ll-button ll-button--text"
              :disabled="busy"
              @click="confirming = false"
            >
              Cancel
            </button>
          </div>
        </div>
        <div v-else class="ll-row">
          <button type="button" class="ll-button ll-button--tonal" @click="confirming = true">
            Disconnect…
          </button>
          <a
            class="ll-button ll-button--text"
            :href="siteUrl('/account')"
            target="_blank"
            rel="noreferrer"
          >
            All connected browsers
          </a>
        </div>
      </template>
      <ConnectPrompt v-else-if="connection === null" />
    </section>

    <section class="ll-card options__card" aria-labelledby="about-heading">
      <h2 id="about-heading">About</h2>
      <p class="ll-muted">
        Version {{ VERSION }}. This extension talks to {{ host }} and to no other site. It sends a
        page's address and title only when you save that page.
      </p>
    </section>
  </main>
</template>

<style scoped>
.options__card,
.options__confirm {
  display: grid;
  gap: 12px;
}
</style>
