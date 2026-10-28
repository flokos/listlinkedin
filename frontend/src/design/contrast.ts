// WCAG 2.2 relative-luminance contrast. Shared by scripts/check-contrast.ts and the
// /design style guide, so both report the same numbers.

export type Rgb = [number, number, number]

export const hexToRgb = (value: string): Rgb => {
  const n = Number.parseInt(value.replace('#', ''), 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

/** `fg` at `alpha` composited over the opaque `bg`. */
export const blend = (fg: Rgb, bg: Rgb, alpha: number): Rgb =>
  fg.map((c, i) => Math.round(c * alpha + bg[i]! * (1 - alpha))) as Rgb

const luminance = ([r, g, b]: Rgb) => {
  const lin = (c: number) => {
    const s = c / 255
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
}

export const contrastRatio = (a: Rgb, b: Rgb) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number]
  return (hi + 0.05) / (lo + 0.05)
}

export const contrast = (fg: string, bg: string) => contrastRatio(hexToRgb(fg), hexToRgb(bg))
