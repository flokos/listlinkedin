// The two permissions the extension asks for only when they are first needed: reading the
// open tabs and the browsing history, for the picker (src/pages/picker). Until the user
// allows one, the extension can't see it; they can take it back on the options page. What is
// read stays in the browser: only the pages the user picks are sent to the site.
import { ext } from './ext'

export type Optional = 'tabs' | 'history'

export const OPTIONAL: readonly Optional[] = ['tabs', 'history']

/** What each one lets the extension read, as the pages say it. */
export const WHAT: Record<Optional, string> = {
  tabs: 'your open tabs',
  history: 'your browsing history',
}

export const isAllowed = (name: Optional): Promise<boolean> =>
  ext().permissions.contains({ permissions: [name] })

/** Asks the user. Browsers only allow this from a click. */
export const allow = (name: Optional): Promise<boolean> =>
  ext().permissions.request({ permissions: [name] })

/** Gives it back. False when the browser keeps it (a build that declares it up front). */
export const takeBack = (name: Optional): Promise<boolean> =>
  ext()
    .permissions.remove({ permissions: [name] })
    .catch(() => false)
