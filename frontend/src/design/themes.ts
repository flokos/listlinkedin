// Semantic color roles for the light and dark themes, built from tokens.ts.
// Components use roles ("primary", "surface-container"), never raw palette values.
// scripts/check-contrast.ts verifies every text/background pairing below.

import { mauve, orchid, status, violet } from './tokens.ts'

export interface ThemeRoles {
  dark: boolean
  colors: Record<string, string>
  /** Opacity of secondary text (Vuetify's medium emphasis) over its background. */
  mediumEmphasis: number
  /** Opacity of disabled content. Exempt from contrast rules (WCAG 1.4.3). */
  disabled: number
  /** Border colour; rendered at `borderOpacity` over the surface. */
  border: string
  borderOpacity: number
}

export const light: ThemeRoles = {
  dark: false,
  colors: {
    background: mauve[50],
    'on-background': mauve[900],
    surface: mauve[0],
    'on-surface': mauve[900],
    'surface-bright': mauve[0],
    'surface-light': mauve[100],
    'surface-container': violet[50],
    'surface-container-high': mauve[100],
    'surface-variant': mauve[800],
    'on-surface-variant': mauve[100],

    primary: violet[700],
    'on-primary': mauve[0],
    'primary-container': violet[100],
    'on-primary-container': violet[900],
    secondary: orchid[700],
    'on-secondary': mauve[0],
    'secondary-container': orchid[100],
    'on-secondary-container': orchid[900],

    outline: mauve[500],
    'outline-variant': mauve[200],
    focus: violet[600],

    error: status.error.strong,
    'on-error': mauve[0],
    'error-container': status.error.container,
    'on-error-container': status.error.onContainer,
    warning: status.warning.strong,
    'on-warning': mauve[0],
    'warning-container': status.warning.container,
    'on-warning-container': status.warning.onContainer,
    success: status.success.strong,
    'on-success': mauve[0],
    'success-container': status.success.container,
    'on-success-container': status.success.onContainer,
    info: status.info.strong,
    'on-info': mauve[0],
    'info-container': status.info.container,
    'on-info-container': status.info.onContainer,
  },
  mediumEmphasis: 0.72,
  disabled: 0.38,
  border: violet[950],
  borderOpacity: 0.14,
}

export const dark: ThemeRoles = {
  dark: true,
  colors: {
    background: mauve[950],
    'on-background': mauve[100],
    surface: mauve[925],
    'on-surface': mauve[100],
    'surface-bright': mauve[850],
    'surface-light': mauve[850],
    'surface-container': '#211833',
    'surface-container-high': mauve[850],
    'surface-variant': mauve[200],
    'on-surface-variant': mauve[900],

    primary: violet[300],
    'on-primary': violet[950],
    'primary-container': violet[800],
    'on-primary-container': violet[100],
    secondary: orchid[300],
    'on-secondary': orchid[950],
    'secondary-container': orchid[800],
    'on-secondary-container': orchid[100],

    outline: mauve[500],
    'outline-variant': mauve[800],
    focus: violet[300],

    error: status.error.soft,
    'on-error': '#3D0612',
    'error-container': '#5C1426',
    'on-error-container': status.error.container,
    warning: status.warning.soft,
    'on-warning': status.warning.onContainer,
    'warning-container': '#4A3000',
    'on-warning-container': status.warning.container,
    success: status.success.soft,
    'on-success': status.success.onContainer,
    'success-container': '#123F27',
    'on-success-container': status.success.container,
    info: status.info.soft,
    'on-info': status.info.onContainer,
    'info-container': '#2C2880',
    'on-info-container': status.info.container,
  },
  mediumEmphasis: 0.74,
  disabled: 0.45,
  border: violet[100],
  borderOpacity: 0.16,
}

export const themes = { light, dark } as const
