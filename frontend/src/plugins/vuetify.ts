import '@fontsource-variable/inter'
import 'vuetify/styles'
import '../design/global.css'

import { createVuetify } from 'vuetify'
import { aliases, mdi } from 'vuetify/iconsets/mdi-svg'

import { defaults } from '../design/defaults'
import { vuetifyThemes } from '../design/vuetify-theme'

export default createVuetify({
  icons: { defaultSet: 'mdi', aliases, sets: { mdi } },
  theme: {
    defaultTheme: 'system',
    themes: vuetifyThemes,
    variations: false,
  },
  defaults,
})
