// The site menu, defined once and rendered by the app bar, the mobile drawer and the footer.
import {
  mdiCompassOutline,
  mdiFolderMultipleOutline,
  mdiFormatListBulletedSquare,
  mdiHomeOutline,
  mdiInformationOutline,
} from '@mdi/js'
import { computed } from 'vue'
import type { RouteLocationNormalizedLoaded, RouteLocationRaw } from 'vue-router'

import { currentUser } from './composables/useSession'

export interface NavItem {
  label: string
  to: RouteLocationRaw
  icon: string
  /** Route names that count as "inside" this item, for the active state. */
  match: string[]
  badge?: 'owned-lists'
  /** Shown only to signed-in visitors. */
  account?: boolean
}

export const mainNav: NavItem[] = [
  { label: 'Home', to: { name: 'home' }, icon: mdiHomeOutline, match: ['home'] },
  {
    label: 'My lists',
    to: { name: 'saved-lists' },
    icon: mdiFormatListBulletedSquare,
    match: ['saved-lists'],
    badge: 'owned-lists',
  },
  {
    label: 'Groups',
    to: { name: 'groups' },
    icon: mdiFolderMultipleOutline,
    match: ['groups', 'group', 'group-list'],
    account: true,
  },
  { label: 'Explore', to: { name: 'explore' }, icon: mdiCompassOutline, match: ['explore'] },
  { label: 'About', to: { name: 'about' }, icon: mdiInformationOutline, match: ['about'] },
]

/** The menu items for this visitor: account pages only when signed in. */
export const shownNav = computed(() => mainNav.filter((item) => !item.account || currentUser()))

/** Secondary links that leave the app (opened in a new tab). */
export const externalNav = [{ label: 'API docs', href: '/api/docs/' }]

const ACCOUNT_PAGES = ['home', 'signin', 'signup', 'reset-password', 'verify-email']

/** The sign-in page, coming back to `from` afterwards unless that is an account page. */
export function signInRoute(from: RouteLocationNormalizedLoaded): RouteLocationRaw {
  if (ACCOUNT_PAGES.includes(String(from.name))) return { name: 'signin' }
  return { name: 'signin', query: { next: from.fullPath } }
}
