// WCAG 2.2 contrast check for the design system. Fails (exit 1) if any pairing used by the
// UI falls below its minimum: 4.5:1 for text (1.4.3), 3:1 for UI parts and focus
// indicators (1.4.11). Run with `npm run check:contrast` (Node strips the types itself).

import { blend, contrastRatio, hexToRgb } from '../src/design/contrast.ts'
import { type ThemeRoles, themes } from '../src/design/themes.ts'
import { avatarTints } from '../src/design/tokens.ts'

const TEXT = 4.5
const UI = 3

interface Pair {
  fg: string
  bg: string
  min: number
  alpha?: number
  label?: string
}

function pairsFor(theme: ThemeRoles): Pair[] {
  const pairs: Pair[] = []
  const c = theme.colors
  // Every role with an on-* partner: text on filled components (buttons, chips, banners).
  for (const role of Object.keys(c)) {
    if (!role.startsWith('on-')) continue
    pairs.push({ fg: role, bg: role.slice(3), min: TEXT })
  }
  const surfaces = ['background', 'surface', 'surface-container', 'surface-container-high']
  for (const bg of surfaces) {
    // Body text and secondary (medium-emphasis) text.
    pairs.push({ fg: 'on-surface', bg, min: TEXT })
    pairs.push({
      fg: 'on-surface',
      bg,
      min: TEXT,
      alpha: theme.mediumEmphasis,
      label: 'secondary text',
    })
    // Coloured text and icons used directly on surfaces (links, tonal buttons, status text).
    for (const fg of ['primary', 'secondary', 'error', 'warning', 'success', 'info']) {
      pairs.push({ fg, bg, min: TEXT })
    }
    // Field outlines and the focus ring must be distinguishable from the surface.
    pairs.push({ fg: 'outline', bg, min: UI })
    pairs.push({ fg: 'focus', bg, min: UI })
  }
  // Tonal (container) variants carry their own text colour.
  pairs.push({ fg: 'primary', bg: 'primary-container', min: TEXT })
  return pairs
}

let failures = 0
for (const [name, theme] of Object.entries(themes)) {
  console.log(`\n${name} theme`)
  for (const p of pairsFor(theme)) {
    const bg = hexToRgb(theme.colors[p.bg]!)
    const fgRaw = theme.colors[p.fg]
    if (!fgRaw) throw new Error(`${name}: unknown role ${p.fg}`)
    const fg = p.alpha ? blend(hexToRgb(fgRaw), bg, p.alpha) : hexToRgb(fgRaw)
    const r = contrastRatio(fg, bg)
    const ok = r >= p.min
    if (!ok) failures++
    const what = `${p.label ?? p.fg} on ${p.bg}`
    console.log(`${ok ? 'ok  ' : 'FAIL'}  ${r.toFixed(2).padStart(5)}:1  (min ${p.min})  ${what}`)
  }
}

console.log('\ndomain avatars (white initials)')
for (const [name, hex] of Object.entries(avatarTints)) {
  const r = contrastRatio(hexToRgb('#FFFFFF'), hexToRgb(hex))
  const ok = r >= TEXT
  if (!ok) failures++
  console.log(
    `${ok ? 'ok  ' : 'FAIL'}  ${r.toFixed(2).padStart(5)}:1  (min ${TEXT})  white on ${name}`,
  )
}

if (failures) {
  console.error(`\n${failures} pairing(s) below WCAG AA.`)
  process.exit(1)
}
console.log('\nAll pairings meet WCAG 2.2 AA.')
