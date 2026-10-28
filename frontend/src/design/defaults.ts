// Global component defaults: the design system's look applied to every Vuetify component,
// so views rarely need to repeat props. Override per use only with a reason.
import type { DefaultsInstance } from 'vuetify'

export const defaults: DefaultsInstance = {
  global: { ripple: true },
  VBtn: { rounded: 'lg', variant: 'flat', class: 'text-none font-weight-semibold' },
  VBtnToggle: { rounded: 'lg', density: 'comfortable' },
  VTextField: { variant: 'outlined', density: 'comfortable', color: 'primary', rounded: 'lg' },
  VTextarea: { variant: 'outlined', density: 'comfortable', color: 'primary', rounded: 'lg' },
  VSelect: { variant: 'outlined', density: 'comfortable', color: 'primary', rounded: 'lg' },
  VCheckbox: { color: 'primary', density: 'comfortable' },
  VCard: { rounded: 'xl', elevation: 0, border: true },
  VSheet: { rounded: 'xl' },
  VChip: { rounded: 'pill', size: 'small', variant: 'tonal' },
  VDialog: { maxWidth: 520, scrollable: true },
  VMenu: { offset: 8 },
  VList: { rounded: 'lg' },
  VListItem: { rounded: 'lg' },
  VTooltip: { location: 'top' },
  VAlert: { rounded: 'lg', variant: 'tonal' },
  VSnackbar: { location: 'bottom', rounded: 'lg', timeout: 4000 },
  VProgressLinear: { color: 'primary' },
  VSkeletonLoader: { color: 'transparent' },
}
