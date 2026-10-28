<script setup lang="ts">
// A letter avatar per site. Deliberately not a remote favicon: fetching icons from other
// sites would leak which links a list contains and break the Content Security Policy.
import { computed } from 'vue'

import { avatarTints } from '../design/tokens'
import { avatarFor } from '../utils/url'

const props = withDefaults(defineProps<{ url: string; size?: number }>(), { size: 40 })
const avatar = computed(() => avatarFor(props.url))
</script>

<template>
  <span
    class="ll-domain-avatar"
    :style="{ width: `${size}px`, height: `${size}px`, background: avatarTints[avatar.tint] }"
    aria-hidden="true"
  >
    {{ avatar.initial }}
  </span>
</template>

<style scoped>
.ll-domain-avatar {
  display: inline-grid;
  place-items: center;
  flex-shrink: 0;
  border-radius: 12px;
  color: #fff;
  font-weight: 700;
  font-size: 1rem;
}
</style>
