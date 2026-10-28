import { ref, watch } from 'vue'
import { useTheme } from 'vuetify'

export type ThemePreference = 'system' | 'light' | 'dark'

const STORAGE_KEY = 'll:theme'
const choices: ThemePreference[] = ['system', 'light', 'dark']

function stored(): ThemePreference {
  const value = localStorage.getItem(STORAGE_KEY)
  return choices.includes(value as ThemePreference) ? (value as ThemePreference) : 'system'
}

const preference = ref<ThemePreference>(stored())

/** The user's light/dark/system choice, persisted and applied to Vuetify. */
export function useThemePreference() {
  const theme = useTheme()
  watch(
    preference,
    (value) => {
      theme.change(value)
      if (value === 'system') localStorage.removeItem(STORAGE_KEY)
      else localStorage.setItem(STORAGE_KEY, value)
    },
    { immediate: true },
  )
  return { preference, isDark: () => theme.current.value.dark }
}
