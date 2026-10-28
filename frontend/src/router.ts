import { createRouter, createWebHistory } from 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    /** Page title; views with dynamic titles (a list's name) set document.title themselves. */
    title?: string
  }
}

const SITE = 'listlinkedin'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('./views/HomeView.vue'),
      meta: { title: 'Share a list of links' },
    },
    {
      path: '/lists',
      name: 'saved-lists',
      component: () => import('./views/SavedListsView.vue'),
      meta: { title: 'Saved lists' },
    },
    {
      path: '/about',
      name: 'about',
      component: () => import('./views/AboutView.vue'),
      meta: { title: 'About & privacy' },
    },
    // Public list URL handed out by the API (`public_url`). nginx serves this app for it.
    {
      path: '/l/:code',
      name: 'list',
      component: () => import('./views/ListView.vue'),
      props: true,
      meta: { title: 'List' },
    },
    // Private edit link: /l/{code}/manage#t={owner token}.
    {
      path: '/l/:code/manage',
      name: 'claim',
      component: () => import('./views/ClaimView.vue'),
      props: true,
      meta: { title: 'Opening your list' },
    },
    // Living style guide: development builds only (tree-shaken from production).
    ...(import.meta.env.DEV
      ? [
          {
            path: '/design',
            name: 'design',
            component: () => import('./views/DesignSystemView.vue'),
            meta: { title: 'Design system' },
          },
        ]
      : []),
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('./views/NotFoundView.vue'),
      meta: { title: 'Page not found' },
    },
  ],
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition // back/forward: restore where the user was
    if (to.hash && !to.hash.startsWith('#t=')) return { el: to.hash, top: 80 }
    if (to.path === from.path) return false // query-only changes (dialogs) keep the scroll
    return { top: 0 }
  },
})

router.afterEach((to, from) => {
  if (to.path === from.path && from.matched.length) return // query/hash only: keep the title
  document.title = to.meta.title ? `${to.meta.title} · ${SITE}` : SITE
})

// After a deploy, an open tab may request page chunks that no longer exist. Reload once
// into the target page to pick up the new build, instead of leaving a blank screen.
const RELOAD_FLAG = 'll:chunk-reload'
router.onError((error, to) => {
  const chunkFailed =
    /dynamically imported module|Importing a module script failed|error loading dynamically imported/i.test(
      String(error?.message ?? error),
    )
  if (chunkFailed && !sessionStorage.getItem(RELOAD_FLAG)) {
    sessionStorage.setItem(RELOAD_FLAG, '1')
    window.location.assign(to.fullPath)
  }
})
router.isReady().then(() => sessionStorage.removeItem(RELOAD_FLAG))

export default router
