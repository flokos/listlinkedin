<script setup lang="ts">
// Living style guide (development builds only, at /design). Shows every token and the
// shared components in their states, rendered by the real theme so it never drifts.
import { mdiCheckCircle, mdiContentCopy, mdiLinkVariant, mdiShareVariant } from '@mdi/js'
import { computed, ref } from 'vue'

import AppLogo from '../components/AppLogo.vue'
import { useThemePreference } from '../composables/useThemePreference'
import { contrast } from '../design/contrast'
import { themes } from '../design/themes'
import { elevation, mauve, orchid, radius, space, violet } from '../design/tokens'

const { preference } = useThemePreference()

const scales = [
  { name: 'Violet', note: 'Brand', values: violet },
  { name: 'Orchid', note: 'Accent', values: orchid },
  { name: 'Mauve', note: 'Neutrals', values: mauve },
]

const textOn = (hex: string) =>
  contrast('#FFFFFF', hex) >= contrast(mauve[950], hex) ? '#FFFFFF' : mauve[950]

const roleGroups = [
  ['primary', 'primary-container', 'secondary', 'secondary-container'],
  ['background', 'surface', 'surface-container', 'surface-container-high'],
  ['error', 'warning', 'success', 'info'],
  ['error-container', 'warning-container', 'success-container', 'info-container'],
]

const activeRoles = computed(() =>
  preference.value === 'dark' ||
  (preference.value === 'system' && matchMedia('(prefers-color-scheme: dark)').matches)
    ? themes.dark
    : themes.light,
)

function roleContrast(role: string) {
  const c = activeRoles.value.colors
  const on = c[`on-${role}`] ?? c['on-surface']!
  return contrast(on, c[role]!)
}

const typeRoles = [
  ['text-display-small', 'Display small', 'Hero headline'],
  ['text-headline-large', 'Headline large', 'Page title'],
  ['text-headline-small', 'Headline small', 'Section title'],
  ['text-title-large', 'Title large', 'Card / dialog title'],
  ['text-title-medium', 'Title medium', 'List item title'],
  ['text-body-large', 'Body large', 'Lead paragraph'],
  ['text-body-medium', 'Body medium', 'Default body copy'],
  ['text-body-small', 'Body small', 'Supporting text'],
  ['text-label-large', 'Label large', 'Buttons'],
  ['text-label-small', 'Label small', 'Chips, metadata'],
]

const fieldValue = ref('https://vuejs.org/guide/')
const checked = ref(true)
</script>

<template>
  <div class="ll-content py-8">
    <header class="d-flex flex-wrap align-center justify-space-between ga-4 mb-8">
      <div>
        <AppLogo :size="40" />
        <h1 class="text-headline-large mt-4">Design system</h1>
        <p class="text-body-large text-medium-emphasis ll-reading">
          Tokens, colour roles and components for listlinkedin. Everything here is rendered by the
          live theme. Usage rules live in <code>docs/design-system.md</code>.
        </p>
      </div>
      <v-btn-toggle v-model="preference" mandatory variant="outlined" color="primary">
        <v-btn value="system">System</v-btn>
        <v-btn value="light">Light</v-btn>
        <v-btn value="dark">Dark</v-btn>
      </v-btn-toggle>
    </header>

    <section class="mb-12" aria-labelledby="ds-palette">
      <h2 id="ds-palette" class="text-headline-small mb-4">Palette</h2>
      <div v-for="scale in scales" :key="scale.name" class="mb-6">
        <p class="text-title-medium mb-2">
          {{ scale.name }}
          <span class="text-medium-emphasis text-body-small">· {{ scale.note }}</span>
        </p>
        <div class="ds-scale">
          <div
            v-for="(hex, step) in scale.values"
            :key="step"
            class="ds-swatch"
            :style="{ background: hex, color: textOn(hex) }"
          >
            <span class="text-label-large">{{ step }}</span>
            <span class="ll-mono">{{ hex }}</span>
          </div>
        </div>
      </div>
    </section>

    <section class="mb-12" aria-labelledby="ds-roles">
      <h2 id="ds-roles" class="text-headline-small mb-1">Colour roles</h2>
      <p class="text-body-medium text-medium-emphasis mb-4">
        Components use roles, never raw palette values. Badges show the contrast of each role's
        <code>on-*</code> text colour (WCAG AA needs 4.5:1).
      </p>
      <div v-for="(group, i) in roleGroups" :key="i" class="ds-roles mb-3">
        <div v-for="role in group" :key="role" class="ds-role pa-4" :class="`bg-${role}`">
          <span class="text-title-small">{{ role }}</span>
          <span class="text-body-small ll-mono">{{ activeRoles.colors[role] }}</span>
          <v-chip size="x-small" variant="flat" class="ds-badge" :prepend-icon="mdiCheckCircle">
            {{ roleContrast(role).toFixed(1) }}:1
          </v-chip>
        </div>
      </div>
    </section>

    <section class="mb-12" aria-labelledby="ds-type">
      <h2 id="ds-type" class="text-headline-small mb-4">Typography</h2>
      <p class="text-body-medium text-medium-emphasis mb-4">
        Inter Variable, self-hosted. MD3 type roles from Vuetify 4.
      </p>
      <v-card>
        <div
          v-for="([cls, name, use], i) in typeRoles"
          :key="cls"
          class="d-flex flex-wrap align-baseline ga-4 px-5 py-3"
          :class="{ 'border-t': i > 0 }"
        >
          <span class="ds-type-meta text-body-small text-medium-emphasis">
            {{ name }}<br /><span class="ll-mono">.{{ cls }}</span>
          </span>
          <span :class="cls">{{ use }}</span>
        </div>
      </v-card>
    </section>

    <section class="mb-12" aria-labelledby="ds-shape">
      <h2 id="ds-shape" class="text-headline-small mb-4">Spacing, radius and elevation</h2>
      <v-row>
        <v-col cols="12" md="4">
          <p class="text-title-medium mb-2">Spacing (4px base)</p>
          <div v-for="(px, key) in space" :key="key" class="d-flex align-center ga-3 mb-1">
            <span class="ll-mono text-body-small" style="width: 3rem">{{ key }}</span>
            <span class="ds-space" :style="{ width: `${px}px` }" />
            <span class="text-body-small text-medium-emphasis">{{ px }}px</span>
          </div>
        </v-col>
        <v-col cols="12" md="4">
          <p class="text-title-medium mb-2">Radius</p>
          <div class="d-flex flex-wrap ga-3">
            <div
              v-for="(px, key) in radius"
              :key="key"
              class="ds-radius d-flex align-end pa-2 text-label-small"
              :style="{ borderRadius: `${Math.min(px, 40)}px` }"
            >
              {{ key }}
            </div>
          </div>
        </v-col>
        <v-col cols="12" md="4">
          <p class="text-title-medium mb-2">Elevation</p>
          <div class="d-flex flex-wrap ga-3">
            <v-sheet
              v-for="(level, key) in elevation"
              :key="key"
              :elevation="level"
              class="ds-elevation d-flex align-end pa-2 text-label-small"
              color="surface"
            >
              {{ key }} · {{ level }}
            </v-sheet>
          </div>
        </v-col>
      </v-row>
    </section>

    <section class="mb-12" aria-labelledby="ds-components">
      <h2 id="ds-components" class="text-headline-small mb-4">Components</h2>
      <v-card class="pa-6 mb-4">
        <p class="text-title-medium mb-3">Buttons</p>
        <div class="d-flex flex-wrap ga-3 mb-2">
          <v-btn color="primary">Primary action</v-btn>
          <v-btn color="primary" variant="tonal">Tonal</v-btn>
          <v-btn color="primary" variant="outlined">Outlined</v-btn>
          <v-btn color="primary" variant="text">Text</v-btn>
          <v-btn color="error" variant="tonal">Destructive</v-btn>
          <v-btn color="primary" disabled>Disabled</v-btn>
          <v-btn color="primary" loading>Loading</v-btn>
          <v-btn :icon="mdiContentCopy" variant="text" aria-label="Copy" />
        </div>
        <p class="text-body-small text-medium-emphasis">
          One primary (filled) button per view. Tonal for secondary actions, text for tertiary.
        </p>
      </v-card>

      <v-card class="pa-6 mb-4">
        <p class="text-title-medium mb-3">Inputs</p>
        <v-row>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="fieldValue"
              label="Link URL"
              hint="http or https"
              persistent-hint
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field
              model-value="ftp://example.com"
              label="Link URL"
              :error-messages="['Only http and https links are allowed.']"
            />
          </v-col>
        </v-row>
        <v-checkbox v-model="checked" label="I've read the guidelines" hide-details />
      </v-card>

      <v-card class="pa-6 mb-4">
        <p class="text-title-medium mb-3">Feedback</p>
        <div class="d-flex flex-wrap ga-2 mb-4">
          <v-chip color="primary">37 / 100 links</v-chip>
          <v-chip color="secondary">New</v-chip>
          <v-chip color="success">Active</v-chip>
          <v-chip color="warning">Expires in 2 days</v-chip>
          <v-chip color="error">Expired</v-chip>
        </div>
        <v-alert type="info" class="mb-2" title="Only people you add can see this list">
          Share it from the Share dialog.
        </v-alert>
        <v-alert type="success" class="mb-2" text="Link added." />
        <v-alert type="warning" class="mb-2" text="This list expires in 2 days." />
        <v-alert type="error" text="That link is already in this list." />
      </v-card>

      <v-card class="pa-6">
        <p class="text-title-medium mb-3">List item</p>
        <v-list class="pa-0" bg-color="transparent">
          <v-list-item
            title="Vue docs"
            subtitle="vuejs.org/guide"
            :prepend-icon="mdiLinkVariant"
            border
          >
            <template #append>
              <v-btn :icon="mdiShareVariant" variant="text" size="small" aria-label="Share" />
            </template>
          </v-list-item>
        </v-list>
      </v-card>
    </section>
  </div>
</template>

<style scoped>
.ds-scale {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(64px, 1fr);
  border-radius: 12px;
  overflow-x: auto;
}
.ds-swatch {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 28px 8px 10px;
  font-size: 0.75rem;
}
.ds-roles {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}
.ds-role {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-height: 112px;
  border-radius: 12px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.ds-badge {
  align-self: flex-start;
  margin-top: auto;
  background: rgb(0 0 0 / 0.18) !important;
  color: inherit !important;
}
.ds-type-meta {
  width: 11rem;
  flex-shrink: 0;
}
.ds-space {
  height: 12px;
  border-radius: 3px;
  background: rgb(var(--v-theme-primary));
}
.ds-radius,
.ds-elevation {
  width: 88px;
  height: 72px;
}
.ds-radius {
  background: rgb(var(--v-theme-primary-container));
  color: rgb(var(--v-theme-on-primary-container));
}
</style>
