// Design tokens: the single source of truth for the listlinkedin design system.
// Everything visual (Vuetify themes, component defaults, the /design style guide and the
// contrast check in scripts/check-contrast.ts) is derived from these values.
// See docs/design-system.md for usage rules.
//
// Plain data with erasable TypeScript only, so Node can run the contrast script directly.

/** Brand violet. 700 is the light-theme primary, 300 the dark-theme primary. */
export const violet = {
  50: '#F6F2FF',
  100: '#EDE5FF',
  200: '#DCCDFE',
  300: '#C3A8FC',
  400: '#A57BF8',
  500: '#8B52F0',
  600: '#7A35E3',
  700: '#6927C8',
  800: '#5822A3',
  900: '#481E83',
  950: '#2D0F5A',
} as const

/** Orchid: a warmer pink-purple accent for highlights and secondary emphasis. */
export const orchid = {
  50: '#FDF2FC',
  100: '#FAE5F9',
  200: '#F5CBF2',
  300: '#EDA2E7',
  400: '#E06DD6',
  500: '#CC45C1',
  600: '#B02CA3',
  700: '#912285',
  800: '#771E6D',
  900: '#631D5B',
  950: '#3E0738',
} as const

/** Mauve: violet-tinted neutrals for surfaces, borders and text. */
export const mauve = {
  0: '#FFFFFF',
  50: '#FAF8FD',
  100: '#F3F0F8',
  200: '#E7E2F0',
  300: '#D4CDE0',
  400: '#ADA4BE',
  500: '#857B98',
  600: '#675E79',
  700: '#4F4760',
  800: '#352E44',
  850: '#2A2139',
  900: '#221C2E',
  925: '#1C1529',
  950: '#140D1F',
} as const

/**
 * Status hues, deliberately muted so they sit with the purple palette. They keep their
 * conventional meaning (red = error, amber = warning, green = success); info is
 * violet-blue. `strong` is for light surfaces, `soft` for dark ones.
 */
export const status = {
  error: { strong: '#B3263E', soft: '#F4A9B6', container: '#FCE8EC', onContainer: '#5C0A1C' },
  warning: { strong: '#8A5300', soft: '#F2C46D', container: '#FDF0D9', onContainer: '#3F2600' },
  success: { strong: '#23784A', soft: '#8FD5A6', container: '#E1F5E8', onContainer: '#0A3A20' },
  info: { strong: '#4B45C6', soft: '#B3B2FF', container: '#E8E7FF', onContainer: '#1D1A6B' },
} as const

export const fontFamily = {
  body: "'Inter Variable', Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
  mono: "ui-monospace, 'SFMono-Regular', 'JetBrains Mono', Menlo, Consolas, monospace",
} as const

/** 4px base unit. Matches Vuetify's spacing helpers (ma-1 = 4px … ma-16 = 64px). */
export const space = {
  0: 0,
  1: 4,
  2: 8,
  3: 12,
  4: 16,
  5: 20,
  6: 24,
  8: 32,
  10: 40,
  12: 48,
  16: 64,
} as const

export const radius = { sm: 4, md: 8, lg: 12, xl: 16, xxl: 24, pill: 9999 } as const

/** MD3 elevation levels (Vuetify 4 supports 0–5). Cards and dialogs use these sparingly. */
export const elevation = { flat: 0, raised: 1, overlay: 3, modal: 5 } as const

export const motion = {
  duration: { fast: 120, base: 200, slow: 320 },
  easing: {
    standard: 'cubic-bezier(0.2, 0, 0, 1)',
    decelerate: 'cubic-bezier(0, 0, 0, 1)',
    accelerate: 'cubic-bezier(0.3, 0, 1, 1)',
  },
} as const

/** Layout widths, in px. */
export const layout = { content: 880, reading: 680, dialog: 520 } as const

/** Domain avatar backgrounds: purple-family hues, all with white initials at >= 4.5:1. */
export const avatarTints = {
  violet: '#6927C8',
  orchid: '#912285',
  plum: '#6B2D5C',
  iris: '#4B45C6',
  lilac: '#7446B0',
  grape: '#481E83',
} as const
