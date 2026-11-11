// Builds the extension into dist/chrome and dist/firefox: the same pages and scripts, with
// each browser's manifest. `--watch` builds again whenever a source changes.
//
//   LL_BASE_URL  the listlinkedin site this build talks to (default: production)
//   LL_GECKO_ID  the add-on ID in Firefox (default: the official one)
import { watch } from 'node:fs'
import { cp, readdir, readFile, rm, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

import vue from '@vitejs/plugin-vue'
import { build, type InlineConfig } from 'vite'

import { type Browser, BROWSERS, manifestFor } from './manifest.ts'
import { siteFrom } from './site.ts'

const root = resolve(import.meta.dirname, '..')
const out = resolve(root, 'dist')
const bundle = resolve(out, '.bundle')
const PAGES = ['popup.html', 'welcome.html', 'options.html', 'offscreen.html']
/** Pages only one browser uses: left out of the other's build. */
const ONLY_IN: Record<string, Browser> = { 'offscreen.html': 'chrome' }

const { version } = JSON.parse(await readFile(resolve(root, 'package.json'), 'utf8')) as {
  version: string
}
const site = siteFrom(process.env.LL_BASE_URL || 'https://listlinkedin.versioncontrol.xyz')
const geckoId = process.env.LL_GECKO_ID || 'extension@listlinkedin.versioncontrol.xyz'

const shared: InlineConfig = {
  root,
  configFile: false,
  logLevel: 'warn',
  define: {
    __LL_BASE_URL__: JSON.stringify(site.origin),
    __LL_VERSION__: JSON.stringify(version),
    'process.env.NODE_ENV': JSON.stringify('production'),
  },
}

// Nothing is minified: the files are small, and readable code is what a reviewer (or
// someone installing a build by hand) can check.

/** The extension's pages: ordinary module scripts and stylesheets, no inline code (CSP). */
const pages: InlineConfig = {
  ...shared,
  plugins: [vue()],
  base: './',
  build: {
    outDir: bundle,
    emptyOutDir: true,
    minify: false,
    modulePreload: { polyfill: false },
    rollupOptions: { input: PAGES.map((page) => resolve(root, page)) },
  },
}

/** One self-contained classic script: what a content script and Firefox's background need. */
const script = (name: string, entry: string): InlineConfig => ({
  ...shared,
  publicDir: false,
  build: {
    outDir: bundle,
    emptyOutDir: false,
    minify: false,
    lib: {
      entry: resolve(root, entry),
      formats: ['iife'],
      name: `ll_${name}`,
      fileName: () => `${name}.js`,
    },
  },
})

async function buildAll() {
  await build(pages)
  await build(script('background', 'src/background/index.ts'))
  await build(script('content', 'src/content/bridge.ts'))
  for (const browser of BROWSERS) {
    const target = resolve(out, browser)
    await rm(target, { recursive: true, force: true })
    await cp(bundle, target, { recursive: true })
    for (const [page, only] of Object.entries(ONLY_IN)) {
      if (only === browser) continue
      await rm(resolve(target, page), { force: true })
      // And its script, which Vite names after the page.
      const name = page.replace(/\.html$/, '')
      for (const file of await readdir(resolve(target, 'assets')))
        if (file.startsWith(`${name}-`)) await rm(resolve(target, 'assets', file))
    }
    const manifest = manifestFor(browser, { version, site, geckoId })
    await writeFile(resolve(target, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`)
  }
  await rm(bundle, { recursive: true, force: true })
  console.log(`Built ${version} for ${site.origin}: dist/${BROWSERS.join(', dist/')}`)
}

await buildAll()

if (process.argv.includes('--watch')) {
  let timer: NodeJS.Timeout | undefined
  let running = Promise.resolve()
  const again = () => {
    clearTimeout(timer)
    timer = setTimeout(() => {
      running = running.then(buildAll).catch((error: unknown) => console.error(error))
    }, 200)
  }
  for (const path of ['src', 'scripts', 'public', ...PAGES])
    watch(resolve(root, path), { recursive: true }, again)
  console.log('Watching for changes…')
}
