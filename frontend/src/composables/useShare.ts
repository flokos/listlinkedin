/** Native share sheet (mobile, some desktops) when the browser supports it. */
export function useShare() {
  const canShare = typeof navigator !== 'undefined' && typeof navigator.share === 'function'
  return {
    canShare,
    async share(data: { title: string; text?: string; url: string }) {
      try {
        await navigator.share(data)
        return true
      } catch {
        return false // dismissed by the user, or not allowed
      }
    },
  }
}
