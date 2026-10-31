<script setup lang="ts">
import { mdiAccountLockOutline, mdiCookieOff, mdiEyeOffOutline, mdiTimerSandEmpty } from '@mdi/js'

const principles = [
  {
    icon: mdiAccountLockOutline,
    title: 'Only an email address',
    text: 'An account needs an email address and a password, nothing else. Your address is for signing in, confirming it is yours and resetting your password. Nobody else sees it; people you share with see the name you choose.',
  },
  {
    icon: mdiEyeOffOutline,
    title: 'You choose who sees a list',
    text: 'Lists start private. Share one with people by email, with anyone who has its link, or make it public in Explore. Search engines are asked not to index any page.',
  },
  {
    icon: mdiCookieOff,
    title: 'No tracking',
    text: "No analytics or third-party scripts; the only cookies keep you signed in. Fonts, QR codes and the links' icons are served from this site, so opening a list tells no other site about you.",
  },
  {
    icon: mdiTimerSandEmpty,
    title: 'You decide how long',
    text: 'Lists last until you delete them, unless you give them an end date. Deleting your account removes everything you own at once and erases it 30 days later; signing in before then brings it back.',
  },
]
</script>

<template>
  <div class="ll-content py-6 py-md-10">
    <h1 class="text-headline-large mb-2">About & privacy</h1>
    <p class="text-body-large text-medium-emphasis ll-reading mb-10">
      listlinkedin makes it easy to collect interesting links for your team and share them with one
      link. Here's how it treats your data.
    </p>

    <v-row class="mb-12">
      <v-col v-for="item in principles" :key="item.title" cols="12" sm="6">
        <v-card class="pa-6 h-100">
          <v-icon :icon="item.icon" color="primary" size="28" class="mb-4" />
          <h2 class="text-title-large mb-2">{{ item.title }}</h2>
          <p class="text-body-medium text-medium-emphasis ma-0">{{ item.text }}</p>
        </v-card>
      </v-col>
    </v-row>

    <section class="ll-reading" aria-labelledby="limits-heading">
      <h2 id="limits-heading" class="text-headline-small mb-4">Limits</h2>
      <v-table class="mb-10 rounded-lg border">
        <tbody>
          <tr>
            <th scope="row">Lifetime of a list</th>
            <td>Until you delete it, or the end date you choose</td>
          </tr>
          <tr>
            <th scope="row">Links per list</th>
            <td>100</td>
          </tr>
          <tr>
            <th scope="row">Length of a link</th>
            <td>2048 characters</td>
          </tr>
          <tr>
            <th scope="row">Allowed links</th>
            <td>http and https only, without passwords in them</td>
          </tr>
          <tr>
            <th scope="row">Tags per list or group</th>
            <td>10</td>
          </tr>
          <tr>
            <th scope="row">Lists per group</th>
            <td>100</td>
          </tr>
          <tr>
            <th scope="row">Images you upload</th>
            <td>PNG, JPEG, WebP or GIF, up to 2 MB</td>
          </tr>
          <tr>
            <th scope="row">New lists</th>
            <td>30 per hour</td>
          </tr>
        </tbody>
      </v-table>

      <h2 class="text-headline-small mb-4">Questions</h2>
      <v-expansion-panels variant="accordion" rounded="xl" class="mb-10">
        <v-expansion-panel title="Do you visit the links people add?">
          <v-expansion-panel-text>
            Once, to show their details: when a link is added or its address changes, our server
            reads the page's title, description and icon. It only visits public addresses, never
            runs the page, and never replaces what you typed. Short links always lead to the
            destination the list's editors set, which they can change at any time.
          </v-expansion-panel-text>
        </v-expansion-panel>

        <v-expansion-panel title="Who can see my email address?">
          <v-expansion-panel-text>
            Only you. People you share lists or groups with see your name, which you set on your
            account page.
          </v-expansion-panel-text>
        </v-expansion-panel>

        <v-expansion-panel title="Something on a public list looks harmful. What can I do?">
          <v-expansion-panel-text>
            Choose “Report…” in the list's or group's ⋮ menu. Your report goes to the people who run
            listlinkedin, not to its owner.
          </v-expansion-panel-text>
        </v-expansion-panel>

        <v-expansion-panel title="I have an edit link from an older list">
          <v-expansion-panel-text>
            Lists made before accounts existed are edited with their private edit link. Open it
            while signed in and choose “Add to my account”: the list becomes yours and the edit link
            stops working. Lost the link? Without it nobody can prove the list is yours. If this
            browser still has it, choose “Show edit link” from the list's menu, or restore a backup
            on the My lists page.
          </v-expansion-panel-text>
        </v-expansion-panel>

        <v-expansion-panel title="Someone else got my edit link. What do I do?">
          <v-expansion-panel-text>
            Open the list and choose “Replace edit link”. The old link stops working immediately;
            save the new one.
          </v-expansion-panel-text>
        </v-expansion-panel>
        <v-expansion-panel title="Is there an API?">
          <v-expansion-panel-text>
            Yes. Everything this site does is available through a documented REST API:
            <a href="/api/docs/" target="_blank" rel="noopener noreferrer" class="text-primary"
              >API docs</a
            >.
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </section>
  </div>
</template>

<style scoped>
th {
  font-weight: 600;
  width: 45%;
}
</style>
