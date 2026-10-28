import { defineConfig, mergeConfig } from 'vitest/config'

import viteConfig from './vite.config.ts'

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      include: ['src/**/*.test.ts'],
      // Vuetify ships CSS imports inside its ESM; let Vite transform it for component tests.
      server: { deps: { inline: ['vuetify'] } },
      css: false,
    },
  }),
)
