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
    :style="{
      width: `${size}px`,
      height: `${size}px`,
      background: avatarTints[avatar.tint],
      fontSize: `${Math.max(16, Math.round(size * 0.4))}px`,
      borderRadius: `${Math.max(12, Math.round(size * 0.2))}px`,
    }"
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
  color: #fff;
  font-weight: 700;
}
</style>
