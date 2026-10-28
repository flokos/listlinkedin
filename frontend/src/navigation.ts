// The site menu, defined once and rendered by the app bar, the mobile drawer and the footer.
import { mdiFormatListBulletedSquare, mdiHomeOutline, mdiInformationOutline } from '@mdi/js'
import type { RouteLocationRaw } from 'vue-router'

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
    to: { name: 'my-lists' },
    icon: mdiFormatListBulletedSquare,
    match: ['my-lists'],
    badge: 'owned-lists',
  },
  { label: 'About', to: { name: 'about' }, icon: mdiInformationOutline, match: ['about'] },
]

/** Secondary links that leave the app (opened in a new tab). */
export const externalNav = [{ label: 'API docs', href: '/api/docs/' }]
