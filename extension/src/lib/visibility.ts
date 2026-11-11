// Who can open a list or a group, in the web app's words (frontend/src/components/ShareDialog.vue).
import type { Visibility } from './storage'

export const VISIBILITIES: readonly Visibility[] = ['private', 'unlisted', 'public']

export const VISIBILITY: Record<Visibility, string> = {
  private: 'Only people you add',
  unlisted: 'Anyone with the link',
  public: 'Public',
}

/**
 * Who a copied link works for. A link never opens more than the list's or group's visibility
 * allows, so this is what to tell whoever copies one. `mine`: this account chooses who.
 */
export function whoCanOpen(visibility: Visibility, kind: 'list' | 'group', mine: boolean): string {
  if (visibility === 'private')
    return mine
      ? 'Only people you add can open this link.'
      : `Only people added to this ${kind} can open this link.`
  return visibility === 'unlisted'
    ? `Anyone with this link can view the ${kind}, but not change it.`
    : `Anyone can view this ${kind}, but not change it.`
}
