// Turns the semantic roles in themes.ts into Vuetify theme definitions.
import type { ThemeDefinition } from 'vuetify'

import { type ThemeRoles, themes } from './themes.ts'
import { mauve, violet } from './tokens.ts'

function toVuetify(roles: ThemeRoles): ThemeDefinition {
  return {
    dark: roles.dark,
    colors: roles.colors,
    variables: {
      'border-color': roles.border,
      'border-opacity': roles.borderOpacity,
      'high-emphasis-opacity': 1,
      'medium-emphasis-opacity': roles.mediumEmphasis,
      'disabled-opacity': roles.disabled,
      'shadow-color': roles.dark ? '#000000' : violet[950],
      'theme-code': roles.dark ? mauve[850] : violet[50],
      'theme-on-code': roles.dark ? violet[100] : violet[900],
      'theme-kbd': roles.dark ? mauve[850] : mauve[100],
      'theme-on-kbd': roles.dark ? mauve[100] : mauve[900],
    },
  }
}

export const vuetifyThemes = {
  light: toVuetify(themes.light),
  dark: toVuetify(themes.dark),
}
