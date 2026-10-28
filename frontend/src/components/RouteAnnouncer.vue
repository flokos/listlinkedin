<script setup lang="ts">
// Single-page navigation doesn't trigger a page load, so screen readers aren't told the
// page changed. After each navigation, announce the new title and move focus to the
// page's <h1> (or <main>) so keyboard users start at the new content.
import { nextTick, ref } from 'vue'
import { useRouter } from 'vue-router'

const message = ref('')
const router = useRouter()
let first = true

router.afterEach((to, from) => {
  if (first) {
    first = false
    return // initial load: the browser already handled it
  }
  if (to.path === from.path) return // query or hash only (dialogs, tabs)
  // Wait for the route transition (out-in) and, for pages that load data first, for their
  // heading to render; fall back to <main> after a second.
  const started = Date.now()
  const settle = async () => {
    await nextTick()
    const heading = document.querySelector<HTMLElement>('main h1')
    if (!heading && Date.now() - started < 1000) return void setTimeout(settle, 100)
    message.value = document.title
    const target = heading ?? document.querySelector<HTMLElement>('main')
    if (target) {
      if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1')
      target.focus({ preventScroll: true })
    }
  }
  setTimeout(settle, 260)
})
</script>

<template>
  <div class="ll-sr-only" role="status" aria-live="polite" aria-atomic="true">{{ message }}</div>
</template>
