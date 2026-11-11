<script setup lang="ts">
// The extension's options: which account this browser is connected to, disconnecting, and
// the keyboard shortcuts as the browser has them now.
import { onBeforeUnmount, onMounted, ref } from 'vue'

import { disconnect } from '../../lib/account'
import { SITE, siteUrl, VERSION } from '../../lib/config'
import { ext } from '../../lib/ext'
import { isAllowed, OPTIONAL, type Optional, takeBack, WHAT } from '../../lib/permissions'
import { type Connection, getConnection, onConnectionChange } from '../../lib/storage'
import BrandMark from '../../ui/BrandMark.vue'
import ConnectPrompt from '../../ui/ConnectPrompt.vue'

const connection = ref<Connection | null>()
const confirming = ref(false)
const busy = ref(false)
const host = new URL(SITE).host
let stop = () => {}

interface Shortcut {
  name: string
  description: string
  keys: string
}
const shortcuts = ref<Shortcut[]>([])

onMounted(async () => {
  connection.value = await getConnection()
  stop = onConnectionChange((next) => (connection.value = next))
  const commands = await ext()
    .commands.getAll()
    .catch(() => [])
  shortcuts.value = commands.map((command) => ({
    name: command.name ?? '',
    description: command.description || 'Open listlinkedin for this page',
    keys: command.shortcut ?? '',
  }))
})
onBeforeUnmount(() => stop())

// What the user allowed the picker to read. Taking it back is one click; asking again
// happens in the picker, when it is next needed.
const reading = ref<Optional[]>([])
async function loadReading() {
  const allowed = await Promise.all(OPTIONAL.map((name) => isAllowed(name).catch(() => false)))
  reading.value = OPTIONAL.filter((_, index) => allowed[index])
}
onMounted(loadReading)
async function stopReading(name: Optional) {
  await takeBack(name)
  await loadReading()
}

// Shortcuts are changed in the browser's own settings: Firefox can open them, Chrome has an
// address for them.
async function changeShortcuts() {
  const commands = ext().commands as typeof chrome.commands & {
    openShortcutSettings?: () => Promise<void>
  }
  if (commands.openShortcutSettings) await commands.openShortcutSettings()
  else await ext().tabs.create({ url: 'chrome://extensions/shortcuts' })
}

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

    <section v-if="shortcuts.length" class="ll-card options__card" aria-labelledby="keys-heading">
      <h2 id="keys-heading">Keyboard shortcuts</h2>
      <dl class="options__keys">
        <template v-for="shortcut in shortcuts" :key="shortcut.name">
          <dt>{{ shortcut.description }}</dt>
          <dd>
            <kbd v-if="shortcut.keys">{{ shortcut.keys }}</kbd>
            <span v-else class="ll-muted">Not set</span>
          </dd>
        </template>
      </dl>
      <p class="ll-muted">
        The last two work on the list you saved to last, without opening anything. A mark on the
        toolbar button says how it went.
      </p>
      <div>
        <button type="button" class="ll-button ll-button--tonal" @click="changeShortcuts">
          Change shortcuts
        </button>
      </div>
    </section>

    <section class="ll-card options__card" aria-labelledby="reading-heading">
      <h2 id="reading-heading">Open tabs and history</h2>
      <p class="ll-muted">
        Saving several pages at once reads your open tabs or your history, in this browser, and only
        after you allow it there. Only the pages you tick are sent.
      </p>
      <p v-if="!reading.length">The extension can read neither now.</p>
      <ul v-else class="options__reading">
        <li v-for="name in reading" :key="name" class="ll-row">
          <span>It can read {{ WHAT[name] }}.</span>
          <button type="button" class="ll-button ll-button--tonal" @click="stopReading(name)">
            Stop reading {{ WHAT[name] }}
          </button>
        </li>
      </ul>
    </section>

    <section class="ll-card options__card" aria-labelledby="about-heading">
      <h2 id="about-heading">About</h2>
      <p class="ll-muted">
        Version {{ VERSION }}. This extension talks to {{ host }} and to no other site. It sends a
        page's address and title only when you save that page, from the popup, a right-click menu or
        a shortcut.
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
.options__reading {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.options__keys {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 6px 16px;
  margin: 0;
}
.options__keys dd {
  margin: 0;
}
.options__keys kbd {
  padding: 2px 6px;
  border: 1px solid var(--ll-outline);
  border-radius: 6px;
  background: var(--ll-background);
  font: inherit;
  font-size: 12px;
}
</style>
