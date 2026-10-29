import { createRouter, createWebHistory } from 'vue-router'

import { trackNavigations } from './composables/useRouteFocus'
import { currentUser, deletionPending, loadSession, sessionKnown } from './composables/useSession'
import { safeRedirectPath } from './utils/url'

declare module 'vue-router' {
  interface RouteMeta {
    /** Page title; views with dynamic titles (a list's name) set document.title themselves. */
    title?: string
    /** Signed-out visitors are sent to sign in first, then back here. */
    requiresAuth?: boolean
    /** Signed-in visitors skip this page (sign-in, sign-up) and continue to `?next=`. */
    guestOnly?: boolean
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
      meta: { title: 'My lists' },
    },
    {
      path: '/about',
      name: 'about',
      component: () => import('./views/AboutView.vue'),
      meta: { title: 'About & privacy' },
    },
    // Accounts. Emailed links carry their key in the fragment (#key=…), never in the path.
    {
      path: '/signin',
      name: 'signin',
      component: () => import('./views/SignInView.vue'),
      meta: { title: 'Sign in', guestOnly: true },
    },
    {
      path: '/signup',
      name: 'signup',
      component: () => import('./views/SignUpView.vue'),
      meta: { title: 'Create your account', guestOnly: true },
    },
    {
      path: '/reset-password',
      name: 'reset-password',
      component: () => import('./views/ResetPasswordView.vue'),
      meta: { title: 'Reset your password' },
    },
    {
      path: '/verify-email',
      name: 'verify-email',
      component: () => import('./views/VerifyEmailView.vue'),
      meta: { title: 'Verify your email' },
    },
    {
      path: '/account/restore',
      name: 'restore-account',
      component: () => import('./views/RestoreAccountView.vue'),
      meta: { title: 'Restore your account', requiresAuth: true },
    },
    {
      path: '/account',
      name: 'account',
      component: () => import('./views/AccountView.vue'),
      meta: { title: 'Your account', requiresAuth: true },
    },
    // Public list URL handed out by the API (`public_url`). nginx serves this app for it.
    {
      path: '/l/:code/:slug?',
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
    // Fragments that carry secrets (#t= edit links, #key= account links) aren't anchors.
    if (to.hash && !/^#(t|key)=/.test(to.hash)) return { el: to.hash, top: 80 }
    if (to.path === from.path) return false // query-only changes (dialogs) keep the scroll
    return { top: 0 }
  },
})

trackNavigations(router)

// Pages that depend on who is signed in wait for the session check; every other page
// renders at once and the check finishes in the background.
// An account being deleted can only be restored or signed out (docs/v2/adr/ADR-016): every
// other page leads to the restore page, which in turn is only for such accounts.
const RESTORE = { name: 'restore-account' } as const

router.beforeEach(async (to) => {
  if (!to.meta.requiresAuth && !to.meta.guestOnly) {
    if (sessionKnown()) return deletionPending() ? RESTORE : undefined
    void loadSession().then(() => {
      if (deletionPending()) void router.replace(RESTORE)
    })
    return
  }
  await loadSession()
  if (to.meta.requiresAuth && !currentUser())
    return { name: 'signin', query: { next: to.fullPath } }
  if (to.name === RESTORE.name) return deletionPending() ? undefined : { name: 'account' }
  if (deletionPending()) return RESTORE
  if (to.meta.guestOnly && currentUser()) return safeRedirectPath(to.query.next)
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
