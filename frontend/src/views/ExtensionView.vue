<script setup lang="ts">
// Where to get the browser extension and how to install it. The files are on GitHub (the
// extension is in no store): this page only links to them.
import { mdiDownload, mdiFirefox, mdiGoogleChrome } from '@mdi/js'

import { extensionDownloads } from '../utils/extensionDownloads'

const browsers = [
  {
    id: 'chrome',
    icon: mdiGoogleChrome,
    title: 'Chrome, Edge, Brave',
    download: 'Download for Chrome',
    href: extensionDownloads.chrome,
    file: 'A zip file, from GitHub',
    steps: [
      'Unzip the file into a folder you will keep.',
      'Open chrome://extensions (edge://extensions in Edge) and turn on “Developer mode”.',
      'Choose “Load unpacked” and pick the folder.',
      'Pin listlinkedin from the Extensions menu (the puzzle piece) to see its button.',
    ],
  },
  {
    id: 'firefox',
    icon: mdiFirefox,
    title: 'Firefox',
    download: 'Download for Firefox',
    href: extensionDownloads.firefox,
    file: 'An add-on file signed by Mozilla, from GitHub',
    steps: [
      'Firefox 140 or later. If Firefox asks whether to install it, choose “Continue to Installation”.',
      'Otherwise open about:addons, the gear, “Install Add-on From File…”, and pick the file.',
      'Choose “Add”. Firefox says what the add-on sends: the address and title of pages you save.',
    ],
  },
]
</script>

<template>
  <div class="ll-content py-6 py-md-10">
    <h1 class="text-headline-large mb-2">Browser extension</h1>
    <p class="text-body-large text-medium-emphasis ll-reading mb-8">
      Save the page you are on into one of your lists, and share your lists, without opening this
      site: from a button on the browser's toolbar, the right-click menu or a keyboard shortcut.
    </p>

    <v-row class="mb-8">
      <v-col v-for="browser in browsers" :key="browser.id" cols="12" md="6">
        <v-card class="pa-6 h-100" :aria-labelledby="`extension-${browser.id}`">
          <div class="d-flex align-center ga-3 mb-4">
            <v-icon :icon="browser.icon" color="primary" size="28" />
            <h2 :id="`extension-${browser.id}`" class="text-title-large">{{ browser.title }}</h2>
          </div>
          <v-btn
            :href="browser.href"
            :prepend-icon="mdiDownload"
            color="primary"
            rel="noopener noreferrer"
            class="mb-2"
          >
            {{ browser.download }}
          </v-btn>
          <p class="text-body-small text-medium-emphasis mb-4">{{ browser.file }}</p>
          <ol class="ll-extension-steps text-body-medium">
            <li v-for="step in browser.steps" :key="step">{{ step }}</li>
          </ol>
        </v-card>
      </v-col>
    </v-row>

    <section class="ll-reading" aria-labelledby="extension-next">
      <h2 id="extension-next" class="text-headline-small mb-3">Then connect it</h2>
      <p class="text-body-large mb-6">
        The extension opens a welcome page. Choose “Connect this browser” there and approve it on
        this site: no password is typed into the extension. Your
        <router-link :to="{ name: 'account' }" class="text-primary">account page</router-link>
        lists the browsers you connected and can disconnect each one.
      </p>

      <h2 class="text-headline-small mb-3">Good to know</h2>
      <ul class="text-body-large ll-extension-notes mb-6">
        <li>
          The extension is not in the Chrome Web Store or on addons.mozilla.org. The files are
          published with each release of listlinkedin on GitHub, and it doesn't update by itself:
          <a
            :href="extensionDownloads.release"
            target="_blank"
            rel="noopener noreferrer"
            class="text-primary"
            >see the latest release</a
          >.
        </li>
        <li>
          It talks only to this site and sends only the pages you save. More in
          <router-link :to="{ name: 'about' }" class="text-primary">About & privacy</router-link>.
        </li>
        <li>
          Permissions, shortcuts, updating and what to do when something is wrong are in the
          <a
            :href="extensionDownloads.guide"
            target="_blank"
            rel="noopener noreferrer"
            class="text-primary"
            >full guide</a
          >.
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.ll-extension-steps,
.ll-extension-notes {
  padding-left: 20px;
}
.ll-extension-steps li,
.ll-extension-notes li {
  margin-bottom: 8px;
}
</style>
