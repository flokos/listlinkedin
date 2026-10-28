// Single-page navigation doesn't trigger a page load, so screen readers aren't told the page
// changed and keyboard focus stays on the clicked link. After each navigation, once the new
// page has rendered its heading, announce its title and move focus to its <h1>.
//
// Deliberately independent of any transition: page fades are a CSS animation (global.css),
// so nothing here waits on animation frames, which background or throttled tabs may not run.
import { nextTick, ref } from 'vue'
import type { Router } from 'vue-router'

export const routeAnnouncement = ref('')

export function trackNavigations(router: Router) {
  let first = true
  let generation = 0
  router.afterEach((to, from, failure) => {
    if (failure) return
    if (first) {
      first = false // initial load: the browser already announced the page
      return
    }
    if (to.path === from.path) return // query or hash only (dialogs)
    const current = ++generation
    const started = Date.now()
    // Pages that load data first (a list) render their heading a little later.
    const settle = async () => {
      await nextTick()
      if (current !== generation) return // a newer navigation took over
      const heading = document.querySelector<HTMLElement>('main h1')
      if (!heading && Date.now() - started < 1500) return void setTimeout(settle, 50)
      routeAnnouncement.value = document.title
      const target = heading ?? document.querySelector<HTMLElement>('main')
      if (!target) return
      if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1')
      target.focus({ preventScroll: true })
    }
    void settle()
  })
}
