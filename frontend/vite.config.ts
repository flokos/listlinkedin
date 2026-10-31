import { fileURLToPath } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import vuetify from 'vite-plugin-vuetify'

// In development the API runs in the `api` container; the dev server forwards API calls,
// short-URL redirects and uploaded images to it so the browser sees a single origin, as
// behind nginx.
const apiTarget = process.env.API_PROXY_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [vue(), vuetify({ autoImport: true })],
  // Vuetify components are auto-imported per file; pre-bundling them makes Vite re-optimize
  // mid-session ("Outdated Optimize Dep"). Vuetify's docs recommend excluding it.
  optimizeDeps: { exclude: ['vuetify'] },
  server: {
    port: 5173,
    // In the dev container, dependencies live in /node_modules, outside the project root.
    fs: { allow: [fileURLToPath(new URL('.', import.meta.url)), '/node_modules'] },
    strictPort: true,
    proxy: {
      '/api/': apiTarget,
      '/r/': apiTarget,
      '/_allauth/': apiTarget,
      '/media/': apiTarget,
    },
  },
})
