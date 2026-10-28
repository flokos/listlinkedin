# Frontend

Vue 3 + Vuetify app for listlinkedin, written in TypeScript and built with Vite. It talks
to the Django API in `../backend` under `/api/v1/` on the same origin.

- **Development:** `docker compose up --build -d` from the repository root starts the Vite
  dev server at http://localhost:5173 with hot reload. It proxies `/api/` and `/r/` to the
  `api` container.
- **Production:** the `prod` target of the [Dockerfile](Dockerfile) builds the app and
  copies it into the nginx image used by `compose.prod.yaml`.

```text
src/
  main.ts             app entry: router + Vuetify
  router.ts           routes; /l/:code is the public list page the API links to
  api.ts              typed client for /api/v1/
  plugins/vuetify.ts  Vuetify setup (SVG Material Design Icons, system light/dark theme)
  views/              one component per route
```
