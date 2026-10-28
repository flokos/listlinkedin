# Frontend

The listlinkedin web app: a Vue 3 + Vuetify 4 single-page app in TypeScript, built with
Vite. It talks to the Django API in `../backend` under `/api/v1/` on the same origin.

- **Development:** run `docker compose up --build -d` from the repository root. That starts
  the Vite dev server at http://localhost:5173 with hot reload. It proxies `/api/` and
  `/r/` to the `api` container. The living style guide is at http://localhost:5173/design.
- **Production:** the `prod` target of the [Dockerfile](Dockerfile) builds the app and
  copies it into the nginx image used by `compose.prod.yaml`.

Visual rules, tokens and component guidance are in
[docs/design-system.md](../docs/design-system.md).

## Pages

| Route                 | Page                                                                                                  |
| --------------------- | ----------------------------------------------------------------------------------------------------- |
| `/`                   | Home: create a list, how it works, recent lists on this device                                        |
| `/l/:code`            | A list. Anyone can view it; owners also get add, edit, delete, rename, share and edit-link management |
| `/l/:code/manage#t=…` | Private edit link: unlocks editing on this device, then opens the list                                |
| `/lists`              | Lists this browser can edit                                                                           |
| `/about`              | Privacy, limits and FAQ                                                                               |
| `/design`             | Style guide (development builds only)                                                                 |

## How ownership works

The API returns a list's owner token once, when the list is created. The app:

1. saves it in `localStorage` (`useOwnedLists`), so this browser can edit the list;
2. gives the user a private **edit link**, `/l/{code}/manage#t={token}`. The token sits in
   the URL fragment, which browsers never send to servers, so it stays out of request logs
   and `Referer` headers. Opening the link on another device saves the token there, and
   the app removes it from the address bar immediately.

"Replace edit link" rotates the token. Other devices then get a clear "your edit link was
replaced" state on their next change.

## Structure

```text
src/
  api.ts               typed API client, ApiError (field errors, Retry-After), NetworkError
  router.ts            routes, titles, scroll restoration, stale-chunk reload
  navigation.ts        the site menu (app bar, drawer, footer)
  design/              tokens, theme roles, Vuetify themes/defaults, global CSS, contrast math
  composables/         useListPage, useOwnedLists, useEditLink, useNotify, useClipboard, …
  components/          shared UI (LinkCard, LinkForm, ShareDialog, EditLinkReveal, …)
  views/               one component per route
  utils/               URL rules (mirroring the server), time formatting, downloads
scripts/check-contrast.ts   WCAG contrast check for the design tokens (runs in CI)
```

## Commands

Run these inside the dev container, for example `docker compose exec frontend npm run test`:

| Command                           | Does                                            |
| --------------------------------- | ----------------------------------------------- |
| `npm run lint`                    | ESLint (Vue, TypeScript)                        |
| `npm run format` / `format:check` | Prettier                                        |
| `npm run type-check`              | `vue-tsc`                                       |
| `npm run test`                    | Vitest unit and component tests (jsdom)         |
| `npm run check:contrast`          | Verifies every colour pairing meets WCAG 2.2 AA |
| `npm run build`                   | Type-check and production build                 |

CI runs all of them.
