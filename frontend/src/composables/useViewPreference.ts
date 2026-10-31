import { ref, watch } from 'vue'

export type LinkView = 'grid' | 'list'

const STORAGE_KEY = 'll:link-view'

function stored(): LinkView {
  return localStorage.getItem(STORAGE_KEY) === 'list' ? 'list' : 'grid'
}

const view = ref<LinkView>(stored())
watch(view, (value) => {
  if (value === 'grid') localStorage.removeItem(STORAGE_KEY)
  else localStorage.setItem(STORAGE_KEY, value)
})

/** Tiles (the default) or rows, remembered on this device for every list. */
export function useViewPreference() {
  return { view }
}
