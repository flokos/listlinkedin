// The site menu, defined once and rendered by the app bar, the mobile drawer and the footer.
import { mdiFormatListBulletedSquare, mdiHomeOutline, mdiInformationOutline } from '@mdi/js'
import type { RouteLocationNormalizedLoaded, RouteLocationRaw } from 'vue-router'

export interface NavItem {
  label: string
  to: RouteLocationRaw
  icon: string
  /** Route names that count as "inside" this item, for the active state. */
  match: string[]
  badge?: 'owned-lists'
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
  { label: 'About', to: { name: 'about' }, icon: mdiInformationOutline, match: ['about'] },
]

/** Secondary links that leave the app (opened in a new tab). */
export const externalNav = [{ label: 'API docs', href: '/api/docs/' }]

const ACCOUNT_PAGES = ['home', 'signin', 'signup', 'reset-password', 'verify-email']

/** The sign-in page, coming back to `from` afterwards unless that is an account page. */
export function signInRoute(from: RouteLocationNormalizedLoaded): RouteLocationRaw {
  if (ACCOUNT_PAGES.includes(String(from.name))) return { name: 'signin' }
  return { name: 'signin', query: { next: from.fullPath } }
}
