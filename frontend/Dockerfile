# syntax=docker/dockerfile:1

FROM node:25-alpine AS deps
ENV NPM_CONFIG_UPDATE_NOTIFIER=false
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund


# Vite dev server against the sources bind-mounted at /app (compose.yaml). Dependencies sit
# in /node_modules, outside the mount, and Node still finds them by walking up from /app.
# They are rebuilt with the image, so `docker compose up --build` picks up lockfile changes.
FROM node:25-alpine AS dev
COPY --from=deps /app/node_modules /node_modules
ENV PATH=/node_modules/.bin:$PATH \
    NPM_CONFIG_UPDATE_NOTIFIER=false
WORKDIR /app
COPY . .
EXPOSE 5173
CMD ["vite", "--host", "0.0.0.0"]


FROM deps AS build
COPY . .
RUN npm run build


# The production proxy: nginx serves the built app and forwards the API to Django. Its
# config is the template mounted by compose.prod.yaml (deploy/nginx/).
FROM nginx:1.30-alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
