import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [vue()],
  // What scripts/build.ts defines for a real build.
  define: {
    __LL_BASE_URL__: JSON.stringify('https://lists.example.test'),
    __LL_VERSION__: JSON.stringify('0.0.0'),
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.ts', 'scripts/**/*.test.ts'],
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
