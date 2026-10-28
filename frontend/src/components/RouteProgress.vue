<script setup lang="ts">
// A thin progress bar while a lazily loaded page is fetched. Shown only after a short
// delay, so fast navigations don't flash it.
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const visible = ref(false)
const router = useRouter()
let timer: ReturnType<typeof setTimeout> | undefined

router.beforeEach(() => {
  clearTimeout(timer)
  timer = setTimeout(() => (visible.value = true), 120)
})
const done = () => {
  clearTimeout(timer)
  visible.value = false
}
router.afterEach(done)
router.onError(done)
</script>

<template>
  <v-progress-linear
    v-if="visible"
    indeterminate
    color="primary"
    height="3"
    class="ll-route-progress"
    aria-label="Loading page"
  />
</template>

<style scoped>
.ll-route-progress {
  position: fixed !important;
  top: 0;
  left: 0;
  right: 0;
  z-index: 2000;
}
</style>
