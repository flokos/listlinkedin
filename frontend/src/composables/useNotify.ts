import { ref } from 'vue'

export interface Toast {
  text: string
  color?: string
  timeout?: number
}

// One queue for the whole app, rendered by <v-snackbar-queue> in App.vue.
const queue = ref<Toast[]>([])

export function useNotify() {
  const push = (toast: Toast) => queue.value.push(toast)
  return {
    queue,
    success: (text: string) => push({ text, color: 'success' }),
    info: (text: string) => push({ text, color: 'surface-variant' }),
    error: (text: string) => push({ text, color: 'error', timeout: 7000 }),
  }
}
