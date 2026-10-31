# Frontend

The listlinkedin web app: a Vue 3 + Vuetify 4 single-page app in TypeScript, built with
Vite. It talks to the Django API in `../backend` on the same origin: `/api/v2/` for lists,
groups and accounts, and `/_allauth/browser/v1/` for sign-up, sign-in and passwords.

- **Development:** run `docker compose up --build -d` from the repository root. That starts
  the Vite dev server at http://localhost:5173 with hot reload. It proxies `/api/`,
  `/_allauth/`, `/r/` and `/media/` to the `api` container. The living style guide is at
  http://localhost:5173/design.
- **Production:** the `prod` target of the [Dockerfile](Dockerfile) builds the app and
  copies it into the nginx image used by `compose.prod.yaml`.

Visual rules, tokens and component guidance are in
[docs/design-system.md](../docs/design-system.md). The architecture is in
[docs/v2/10-FRONTEND-ARCHITECTURE.md](../docs/v2/10-FRONTEND-ARCHITECTURE.md).

## Pages

| Route                                                    | Page                                                                              |
| -------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `/`                                                      | Home: create a list, how it works                                                 |
| `/lists`                                                 | My lists: the lists in your account, owned or shared with you                     |
| `/l/:code/:slug?`                                        | A list. Who sees it and what they may do comes from the server (`permissions`)    |
| `/l/:code/settings`, `/l/:code/history`                  | A list's settings, and its versions with restore                                  |
| `/l/:code/manage`                                        | V1's edit-link address: redirects to the list (edit links were retired in v2.1.0) |
| `/groups`, `/g/:code/:slug?`, `/g/:code/l/:listCode`     | Your groups, and a group's workspace with its sidebar                             |
| `/explore`                                               | Public lists and groups, with search and tags                                     |
| `/signin`, `/signup`, `/verify-email`, `/reset-password` | Accounts (allauth's headless API)                                                 |
| `/account`, `/account/restore`                           | Your account; restoring one that is being deleted                                 |
| `/about`                                                 | Privacy, limits and FAQ                                                           |
| `/design`                                                | Style guide (development builds only)                                             |

## Accounts and permissions

Every list belongs to an account. The session cookie identifies the user, and unsafe
requests send Django's CSRF token (`api/client.ts`). The app never decides who may do what:
each list and group comes with `permissions` from the server's policy, and the UI shows only
those actions. (Until v2.1.0, lists from before accounts were also managed with an edit link
saved in the browser.)

## Structure

```text
src/
  api/                 typed API client per resource, ApiError (field errors, Retry-After), NetworkError
  router.ts            routes, titles, scroll restoration, stale-chunk reload
  navigation.ts        the site menu (app bar, drawer, footer)
  design/              tokens, theme roles, Vuetify themes/defaults, global CSS, contrast math
  composables/         useListPage, useSession, useNotify, useClipboard, …
  components/          shared UI (LinkTile, LinkCard, ShareDialog, GroupSidebar, …)
  views/               one component per route
  utils/               URL rules (mirroring the server), time formatting, history wording
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
