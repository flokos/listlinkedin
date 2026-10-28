import { useNotify } from './useNotify'

async function writeText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    // Clipboard API unavailable (insecure context, old browser): legacy fallback.
    const area = document.createElement('textarea')
    area.value = text
    area.setAttribute('readonly', '')
    area.style.position = 'fixed'
    area.style.opacity = '0'
    document.body.append(area)
    area.select()
    const ok = document.execCommand('copy')
    area.remove()
    return ok
  }
}

export function useClipboard() {
  const notify = useNotify()
  return {
    /** Copies `text` and confirms with a toast naming what was copied. */
    async copy(text: string, what = 'Link') {
      if (await writeText(text)) notify.success(`${what} copied to clipboard`)
      else notify.error(`Couldn't copy. Select the text and copy it manually.`)
    },
  }
}
