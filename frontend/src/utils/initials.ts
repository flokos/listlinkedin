/** Up to two letters standing for a title: the first letters of its first two words. */
export function initialsOf(title: string): string {
  const words = title.trim().split(/\s+/).filter(Boolean)
  if (!words.length) return '?'
  const letters =
    words.length > 1 ? [...words[0]!][0]! + [...words[1]!][0]! : [...words[0]!].slice(0, 2).join('')
  return letters.toUpperCase()
}
