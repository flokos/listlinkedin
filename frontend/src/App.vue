<template>
  <v-app>
    <v-app-bar flat border="b">
      <v-app-bar-title>
        <router-link to="/" class="text-decoration-none text-high-emphasis">listlinkedin</router-link>
      </v-app-bar-title>
    </v-app-bar>
    <v-main>
      <v-container max-width="840">
        <router-view />
      </v-container>
    </v-main>
  </v-app>
</template>
