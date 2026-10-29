<script setup lang="ts">
import { externalNav, shownNav } from '../navigation'
</script>

<template>
  <footer class="ll-footer mt-16 border-t">
    <div
      class="ll-content d-flex flex-column flex-sm-row ga-4 align-sm-center justify-space-between px-4 py-8"
    >
      <p class="text-body-small text-medium-emphasis ma-0">
        Lists are private until you share them.
      </p>
      <nav aria-label="Footer" class="d-flex flex-wrap ga-4 text-body-small">
        <router-link
          v-for="item in shownNav"
          :key="item.label"
          :to="item.to"
          class="ll-footer__link"
        >
          {{ item.label }}
        </router-link>
        <a
          v-for="link in externalNav"
          :key="link.label"
          :href="link.href"
          target="_blank"
          rel="noopener noreferrer"
          class="ll-footer__link"
        >
          {{ link.label }}
        </a>
      </nav>
    </div>
  </footer>
</template>

<style scoped>
.ll-footer__link {
  color: rgb(var(--v-theme-on-surface));
  opacity: var(--v-medium-emphasis-opacity);
  text-decoration: none;
}
.ll-footer__link:hover {
  opacity: 1;
  text-decoration: underline;
}
</style>
