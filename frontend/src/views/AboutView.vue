<script setup lang="ts">
import { mdiCookieOff, mdiEyeOffOutline, mdiShieldKeyOutline, mdiTimerSandEmpty } from '@mdi/js'

const principles = [
  {
    icon: mdiEyeOffOutline,
    title: 'No accounts',
    text: "We don't ask for a name or email. A list is reached by a long random address, and search engines are asked not to index it.",
  },
  {
    icon: mdiShieldKeyOutline,
    title: 'Private edit links',
    text: "Edit access is a secret link that's shown once. The secret part sits after the #, which browsers never send to servers, so it doesn't end up in logs.",
  },
  {
    icon: mdiCookieOff,
    title: 'No tracking',
    text: 'No cookies, analytics or third-party scripts. Fonts and QR codes are served from this site.',
  },
  {
    icon: mdiTimerSandEmpty,
    title: 'Temporary by design',
    text: 'Every list expires 30 days after it was created, and its data is deleted within a day after that.',
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
            <td>30 days</td>
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
            <th scope="row">New lists</th>
            <td>30 per hour from one network</td>
          </tr>
        </tbody>
      </v-table>

      <h2 class="text-headline-small mb-4">Questions</h2>
      <v-expansion-panels variant="accordion" rounded="xl" class="mb-10">
        <v-expansion-panel title="Do you check the links people add?">
          <v-expansion-panel-text>
            We check that a link is well-formed and uses http or https, but we never visit it. Short
            links always lead to the destination the list's creator set, which they can change at
            any time.
          </v-expansion-panel-text>
        </v-expansion-panel>
        <v-expansion-panel title="I lost my edit link. Can you recover it?">
          <v-expansion-panel-text>
            No. Without accounts there's no way to prove the list is yours. If this browser still
            has edit access, open the list and choose “Show edit link” from its menu.
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
