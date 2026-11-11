<script setup lang="ts">
// The toolbar popup. Not connected: "Connect this browser". Connected: save this page, or
// look into your lists and share them. It also says how the last right-click or shortcut
// went, if that needs saying. Opened with `?url=…` in a small window of its own, it is about
// that address: "Choose a list…" in the right-click menu.
import { onBeforeUnmount, onMounted, ref } from 'vue'

import { ext } from '../lib/ext'
import { clearMark } from '../lib/feedback'
import {
  type Connection,
  getConnection,
  onConnectionChange,
  type Outcome,
  takeOutcome,
} from '../lib/storage'
import BrandMark from '../ui/BrandMark.vue'
import ConnectPrompt from '../ui/ConnectPrompt.vue'
import NoticeBox from '../ui/NoticeBox.vue'
import BrowsePanel from './BrowsePanel.vue'
import SavePanel from './SavePanel.vue'

const connection = ref<Connection | null>()
/** The connection ended while the popup was open. */
const ended = ref(false)
/** How the last thing done without a window went, when it didn't simply work. */
const outcome = ref<Outcome | null>(null)
const view = ref<'save' | 'lists'>('save')
/** "My lists" is only loaded once it is asked for, and then kept. */
const browsed = ref(false)
const ownWindow = new URLSearchParams(window.location.search).has('url')
let stop = () => {}

onMounted(async () => {
  connection.value = await getConnection()
  stop = onConnectionChange((next) => {
    // Connected a moment ago and now not: the site ended it while the popup was open (the
    // account is forgotten before the request that found out has finished failing).
    ended.value = Boolean(connection.value) && !next
    connection.value = next
  })
  outcome.value = await takeOutcome().catch(() => null)
  await clearMark().catch(() => {}) // whatever the button's mark was about is being read now
})
onBeforeUnmount(() => stop())

function show(next: 'save' | 'lists') {
  view.value = next
  if (next === 'lists') browsed.value = true
}

function disconnected() {
  ended.value = true
  connection.value = null
}

const options = () => ext().runtime.openOptionsPage()
/** The page for saving several pages at once: a tab of its own, with room for a long list. */
const picker = (source: 'tabs' | 'history') => ext().runtime.getURL(`picker.html?source=${source}`)
// The Connect page opens in a new tab; a popup would close by itself, a page stays.
const started = () => window.close()
</script>

<template>
  <main class="popup" :class="{ 'popup--window': ownWindow }">
    <header class="popup__header">
      <BrandMark />
      <button type="button" class="ll-button ll-button--text" @click="options">Options</button>
    </header>
    <h1 class="ll-visually-hidden">listlinkedin</h1>
    <NoticeBox v-if="outcome" :tone="outcome.tone">{{ outcome.text }}</NoticeBox>
    <p v-if="connection === undefined" class="ll-muted" aria-busy="true">Loading…</p>
    <ConnectPrompt v-else-if="connection === null" :ended="ended" @started="started" />
    <template v-else>
      <div class="popup__views" role="group" aria-label="Show">
        <button
          type="button"
          class="popup__view"
          :aria-pressed="view === 'save'"
          @click="show('save')"
        >
          Save this page
        </button>
        <button
          type="button"
          class="popup__view"
          :aria-pressed="view === 'lists'"
          @click="show('lists')"
        >
          My lists
        </button>
      </div>
      <SavePanel v-show="view === 'save'" @disconnected="disconnected" />
      <BrowsePanel v-if="browsed" v-show="view === 'lists'" @disconnected="disconnected" />
      <p v-show="view === 'save'" class="popup__more">
        Save several:
        <a :href="picker('tabs')" target="_blank" rel="noreferrer">open tabs</a> ·
        <a :href="picker('history')" target="_blank" rel="noreferrer">from history</a>
      </p>
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
.popup--window {
  margin: 0 auto;
}
.popup__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.popup__views {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  padding: 3px;
  border-radius: 999px;
  background: var(--ll-outline-variant);
}
.popup__view {
  min-height: 30px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--ll-on-surface);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}
.popup__view[aria-pressed='true'] {
  background: var(--ll-surface);
  color: var(--ll-primary);
}
.popup__more {
  font-size: 12px;
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
