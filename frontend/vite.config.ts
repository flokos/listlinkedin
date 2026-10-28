import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import vuetify from 'vite-plugin-vuetify'

// In development the API runs in the `api` container; the dev server forwards API calls
// and short-URL redirects to it so the browser sees a single origin, as behind nginx.
const apiTarget = process.env.API_PROXY_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [vue(), vuetify({ autoImport: true })],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api/': apiTarget,
      '/r/': apiTarget,
    },
  },
})
