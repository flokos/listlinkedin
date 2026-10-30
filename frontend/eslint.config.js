import js from '@eslint/js'
import prettier from 'eslint-config-prettier'
import pluginVue from 'eslint-plugin-vue'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist/', 'node_modules/'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  {
    files: ['**/*.vue'],
    languageOptions: { parserOptions: { parser: tseslint.parser } },
  },
  {
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    rules: {
      // Views are named by route (HomeView), components by role; single words are fine for views.
      'vue/multi-word-component-names': 'off',
      // User and fetched text is only ever rendered as text (docs/v2/13-SECURITY.md, XSS).
      // The recommended config merely warns, and warnings don't fail the lint.
      'vue/no-v-html': 'error',
    },
  },
  prettier, // formatting is Prettier's job
)
